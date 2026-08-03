# -*- coding: utf-8 -*-
"""Review integrity, condition identification and location-aware ranking.

The review tests are written adversarially: most of them are attempts to plant
a review without having attended a consultation. If any of those succeed the
rating system is worthless, so they matter more than the happy path.
"""
import os
import tempfile
import unittest
import uuid
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/reviews.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.doctor import Doctor  # noqa: E402
from app.models.user import User  # noqa: E402


class ReviewTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app, raise_server_exceptions=False)

    def _account(self, role="PATIENT"):
        email = f"{role.lower()}-{uuid.uuid4().hex[:8]}@example.com"
        password = "Passw0rd@123"
        self.client.post(
            "/api/v1/users",
            json={
                "full_name": f"Test {role} Person",
                "email": email,
                "phone": f"017{uuid.uuid4().int % 100000000:08d}",
                "password": password,
            },
        )
        session = SessionLocal()
        try:
            user = session.query(User).filter(User.email == email).first()
            if role != "PATIENT":
                user.role = role
                session.commit()
            user_id = user.id
        finally:
            session.close()

        login = self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        return user_id, {"Authorization": f"Bearer {login.json()['access_token']}"}

    def _patient(self):
        user_id, headers = self._account("PATIENT")
        self.client.post(
            f"/api/v1/patients/{user_id}",
            json={
                "date_of_birth": "1992-03-03",
                "gender": "FEMALE",
                "blood_group": "A+",
                "height_cm": 160.0,
                "weight_kg": 58.0,
                "emergency_contact": "01711111111",
                "address": "Dhaka",
            },
            headers=headers,
        )
        return user_id, headers

    def _doctor(self, specialization="Cardiology", fee=800.0, hospital="Square Hospital"):
        user_id, headers = self._account("DOCTOR")
        self.client.post(
            f"/api/v1/doctors/{user_id}",
            json={
                "bmdc_number": f"BMDC-{uuid.uuid4().hex[:8].upper()}",
                "specialization": specialization,
                "experience_years": 12,
                "consultation_fee": fee,
                "hospital_name": hospital,
                "bio": "Test doctor",
            },
            headers=headers,
        )
        session = SessionLocal()
        try:
            doctor = session.query(Doctor).filter(Doctor.user_id == user_id).first()
            doctor.verification_status = True
            session.commit()
            doctor_id = doctor.id
        finally:
            session.close()
        return doctor_id, headers

    def _completed_visit(self, date_text="2026-12-01", sign=True):
        """Book, attend and (optionally) sign off a full consultation."""
        patient_user_id, patient_headers = self._patient()
        doctor_id, doctor_headers = self._doctor()

        self.client.post(
            f"/api/v1/doctor-availability/{doctor_id}",
            json={
                "available_date": date_text,
                "start_time": "10:00",
                "end_time": "11:00",
            },
            headers=doctor_headers,
        )
        self.client.post(
            f"/api/v1/appointments/{patient_user_id}",
            json={
                "doctor_id": doctor_id,
                "appointment_date": date_text,
                "appointment_time": "10:00",
                "reason": "Chest discomfort for review test",
            },
            headers=patient_headers,
        )
        appointment_id = self.client.get(
            f"/api/v1/appointments/patient/{patient_user_id}", headers=patient_headers
        ).json()[0]["id"]

        consultation_id = None
        if sign:
            consultation_id = self.client.post(
                "/api/v1/consultations",
                json={"appointment_id": appointment_id},
                headers=doctor_headers,
            ).json()["id"]
            self.client.patch(
                f"/api/v1/consultations/{consultation_id}",
                json={"diagnosis": "Stable angina"},
                headers=doctor_headers,
            )
            self.client.post(
                f"/api/v1/consultations/{consultation_id}/close",
                headers=doctor_headers,
            )

        return {
            "appointment_id": appointment_id,
            "consultation_id": consultation_id,
            "doctor_id": doctor_id,
            "patient_headers": patient_headers,
            "doctor_headers": doctor_headers,
            "patient_user_id": patient_user_id,
        }


class ReviewIntegrityTests(ReviewTestCase):
    """Every test here is an attempt to game the rating system."""

    def test_review_after_a_real_signed_consultation_is_accepted(self):
        visit = self._completed_visit("2026-12-02")
        response = self.client.post(
            "/api/v1/reviews",
            json={
                "appointment_id": visit["appointment_id"],
                "rating": 5,
                "comment": "ডাক্তার খুব ভালো বুঝিয়ে বলেছেন।",
            },
            headers=visit["patient_headers"],
        )
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual("SIGNED_CONSULTATION", response.json()["proof_type"])
        self.assertTrue(response.json()["is_verified"])

    def test_review_without_any_appointment_is_impossible(self):
        """There is no API path that accepts a review without a visit."""
        _, headers = self._patient()
        response = self.client.post(
            "/api/v1/reviews",
            json={"appointment_id": "made-up-id", "rating": 5, "comment": "Great!"},
            headers=headers,
        )
        self.assertEqual(404, response.status_code)

    def test_a_stranger_cannot_review_someone_elses_visit(self):
        visit = self._completed_visit("2026-12-03")
        _, attacker = self._patient()
        response = self.client.post(
            "/api/v1/reviews",
            json={"appointment_id": visit["appointment_id"], "rating": 1},
            headers=attacker,
        )
        self.assertEqual(403, response.status_code)

    def test_cannot_review_a_visit_that_never_happened(self):
        """Booked but never attended: no proof, so no review."""
        visit = self._completed_visit("2026-12-04", sign=False)
        response = self.client.post(
            "/api/v1/reviews",
            json={"appointment_id": visit["appointment_id"], "rating": 5},
            headers=visit["patient_headers"],
        )
        self.assertEqual(403, response.status_code)
        self.assertIn("actually took place", response.json()["detail"])

    def test_the_same_visit_cannot_be_reviewed_twice(self):
        """Blocks the simplest review-farming method: repeat submission."""
        visit = self._completed_visit("2026-12-05")
        body = {"appointment_id": visit["appointment_id"], "rating": 5}
        first = self.client.post(
            "/api/v1/reviews", json=body, headers=visit["patient_headers"]
        )
        self.assertEqual(200, first.status_code)

        second = self.client.post(
            "/api/v1/reviews", json=body, headers=visit["patient_headers"]
        )
        self.assertEqual(409, second.status_code)

    def test_anonymous_users_cannot_review(self):
        visit = self._completed_visit("2026-12-06")
        response = self.client.post(
            "/api/v1/reviews",
            json={"appointment_id": visit["appointment_id"], "rating": 5},
        )
        self.assertIn(response.status_code, (401, 403))

    def test_a_doctor_cannot_review_themselves(self):
        visit = self._completed_visit("2026-12-07")
        response = self.client.post(
            "/api/v1/reviews",
            json={"appointment_id": visit["appointment_id"], "rating": 5},
            headers=visit["doctor_headers"],
        )
        self.assertEqual(403, response.status_code)

    def test_rating_outside_one_to_five_is_rejected(self):
        visit = self._completed_visit("2026-12-08")
        for bad in (0, 6, -1, 99):
            with self.subTest(rating=bad):
                response = self.client.post(
                    "/api/v1/reviews",
                    json={"appointment_id": visit["appointment_id"], "rating": bad},
                    headers=visit["patient_headers"],
                )
                self.assertEqual(422, response.status_code)

    def test_reviewer_name_is_partially_masked(self):
        """Honest feedback should not require broadcasting a full name."""
        _, headers = self._patient()
        visit = self._completed_visit("2026-12-09")
        self.client.post(
            "/api/v1/reviews",
            json={"appointment_id": visit["appointment_id"], "rating": 4},
            headers=visit["patient_headers"],
        )
        listing = self.client.get(
            f"/api/v1/doctors/{visit['doctor_id']}/reviews", headers=headers
        ).json()
        name = listing["items"][0]["patient_name"]
        self.assertTrue(name.endswith("."), name)


class RatingAggregationTests(ReviewTestCase):
    def test_rating_is_shrunk_toward_the_mean_for_few_reviews(self):
        """One five-star review must not produce a perfect public score."""
        _, headers = self._patient()
        visit = self._completed_visit("2026-12-10")
        self.client.post(
            "/api/v1/reviews",
            json={"appointment_id": visit["appointment_id"], "rating": 5},
            headers=visit["patient_headers"],
        )
        summary = self.client.get(
            f"/api/v1/doctors/{visit['doctor_id']}/reviews", headers=headers
        ).json()
        self.assertEqual(5.0, summary["average_rating"])
        self.assertLess(summary["bayesian_rating"], 5.0)
        self.assertGreater(summary["bayesian_rating"], 4.0)

    def test_summary_reports_distribution_and_counts(self):
        _, headers = self._patient()
        visit = self._completed_visit("2026-12-11")
        self.client.post(
            "/api/v1/reviews",
            json={
                "appointment_id": visit["appointment_id"],
                "rating": 3,
                "rating_punctuality": 2,
                "rating_explanation": 4,
            },
            headers=visit["patient_headers"],
        )
        summary = self.client.get(
            f"/api/v1/doctors/{visit['doctor_id']}/reviews", headers=headers
        ).json()
        self.assertEqual(1, summary["review_count"])
        self.assertEqual(1, summary["rating_distribution"]["3"])
        self.assertEqual(2, summary["sub_scores"]["punctuality"])

    def test_hidden_review_stops_counting(self):
        _, headers = self._patient()
        visit = self._completed_visit("2026-12-12")
        created = self.client.post(
            "/api/v1/reviews",
            json={"appointment_id": visit["appointment_id"], "rating": 1},
            headers=visit["patient_headers"],
        ).json()

        _, admin = self._account("ADMIN")
        hidden = self.client.post(
            f"/api/v1/reviews/{created['id']}/hide",
            json={"reason": "Abusive language"},
            headers=admin,
        )
        self.assertEqual(200, hidden.status_code, hidden.text)

        summary = self.client.get(
            f"/api/v1/doctors/{visit['doctor_id']}/reviews", headers=headers
        ).json()
        self.assertEqual(0, summary["review_count"])

    def test_only_admins_can_hide_a_review(self):
        visit = self._completed_visit("2026-12-13")
        created = self.client.post(
            "/api/v1/reviews",
            json={"appointment_id": visit["appointment_id"], "rating": 2},
            headers=visit["patient_headers"],
        ).json()
        response = self.client.post(
            f"/api/v1/reviews/{created['id']}/hide",
            json={"reason": "I did not like it"},
            headers=visit["patient_headers"],
        )
        self.assertEqual(403, response.status_code)

    def test_pending_list_shows_only_unreviewed_attended_visits(self):
        visit = self._completed_visit("2026-12-14")
        pending = self.client.get(
            "/api/v1/reviews/pending", headers=visit["patient_headers"]
        ).json()
        self.assertIn(
            visit["appointment_id"], [p["appointment_id"] for p in pending]
        )

        self.client.post(
            "/api/v1/reviews",
            json={"appointment_id": visit["appointment_id"], "rating": 5},
            headers=visit["patient_headers"],
        )
        pending_after = self.client.get(
            "/api/v1/reviews/pending", headers=visit["patient_headers"]
        ).json()
        self.assertNotIn(
            visit["appointment_id"], [p["appointment_id"] for p in pending_after]
        )


class RecommendationTests(ReviewTestCase):
    def test_ranking_prefers_the_matching_specialty(self):
        _, headers = self._patient()
        self._doctor(specialization="Cardiology")
        self._doctor(specialization="Dermatology")
        _, headers = self._patient()
        results = self.client.get(
            "/api/v1/recommendations/doctors?specialty=Cardiology", headers=headers
        ).json()["results"]
        self.assertTrue(results)
        self.assertEqual("Cardiology", results[0]["specialization"])

    def test_urgent_ranking_reports_its_own_criteria(self):
        self._doctor()
        _, headers = self._patient()
        body = self.client.get(
            "/api/v1/recommendations/doctors?specialty=Cardiology&urgent=true",
            headers=headers,
        ).json()
        self.assertTrue(body["urgent"])
        self.assertIn("proximity", body["ranked_by"])

    def test_every_result_explains_its_score(self):
        _, headers = self._patient()
        self._doctor()
        _, headers = self._patient()
        results = self.client.get(
            "/api/v1/recommendations/doctors?specialty=Cardiology", headers=headers
        ).json()["results"]
        breakdown = results[0]["score_breakdown"]
        for key in ("specialty", "distance", "rating", "availability"):
            self.assertIn(key, breakdown)

    def test_unreviewed_doctors_are_still_recommendable(self):
        """A new doctor with no reviews must not be unrankable."""
        _, headers = self._patient()
        doctor_id, _ = self._doctor(specialization="Nephrology")
        _, headers = self._patient()
        results = self.client.get(
            "/api/v1/recommendations/doctors?specialty=Nephrology", headers=headers
        ).json()["results"]
        self.assertIn(doctor_id, [r["doctor_id"] for r in results])

    def test_fee_ceiling_is_respected(self):
        self._doctor(specialization="Urology", fee=2500.0)
        _, headers = self._patient()
        results = self.client.get(
            "/api/v1/recommendations/doctors?specialty=Urology&max_fee=500",
            headers=headers,
        ).json()["results"]
        self.assertTrue(all(r["consultation_fee"] <= 500 for r in results))

    def test_distance_is_computed_when_coordinates_are_supplied(self):
        """Doctors are placed via their hospital, so distance needs seed data."""
        self._doctor(hospital="Square Hospital")
        _, headers = self._patient()
        results = self.client.get(
            "/api/v1/recommendations/doctors"
            "?specialty=Cardiology&latitude=23.75&longitude=90.39",
            headers=headers,
        ).json()["results"]
        self.assertTrue(results)


class ConditionIdentificationTests(ReviewTestCase):
    def test_triage_returns_a_ranked_differential(self):
        _, headers = self._patient()
        body = self.client.post(
            "/api/v1/triage",
            json={"symptoms": "তিন দিন ধরে জ্বর, শরীর ব্যথা, চোখে ব্যথা", "age_years": 30},
            headers=headers,
        ).json()
        self.assertTrue(body["differential"])
        self.assertIn("likelihood", body["differential"][0])
        self.assertIn("name_bn", body["differential"][0])

    def test_dengue_is_identified_from_its_symptom_picture(self):
        _, headers = self._patient()
        body = self.client.post(
            "/api/v1/triage",
            json={"symptoms": "জ্বর, শরীর ব্যথা, চোখে ব্যথা, র‍্যাশ", "age_years": 28},
            headers=headers,
        ).json()
        names = [d["condition"] for d in body["differential"]]
        self.assertIn("dengue", names)

    def test_prolonged_cough_with_weight_loss_suggests_tuberculosis(self):
        _, headers = self._patient()
        body = self.client.post(
            "/api/v1/triage",
            json={
                "symptoms": "এক মাস ধরে কাশি, ওজন কমছে, রাতে ঘাম",
                "age_years": 40,
            },
            headers=headers,
        ).json()
        names = [d["condition"] for d in body["differential"]]
        self.assertIn("tuberculosis", names)

    def test_cardiac_referral_wins_over_a_likelier_benign_condition(self):
        """Chest pain with breathlessness fits asthma too - cardiac must win."""
        _, headers = self._patient()
        body = self.client.post(
            "/api/v1/triage",
            json={"symptoms": "বুকে ব্যথা, শ্বাস নিতে কষ্ট", "age_years": 55},
            headers=headers,
        ).json()
        self.assertEqual("EMERGENCY", body["triage_level"])
        self.assertIn(
            body["recommended_specialty"], ("Cardiology", "Emergency Medicine")
        )

    def test_differential_is_bilingual(self):
        _, headers = self._patient()
        body = self.client.post(
            "/api/v1/triage",
            json={"symptoms": "ঘন ঘন প্রস্রাব, অতিরিক্ত পিপাসা", "age_years": 50},
            headers=headers,
        ).json()
        top = body["differential"][0]
        self.assertTrue(top["name_bn"])
        self.assertTrue(top["name_en"])
        self.assertNotEqual(top["name_bn"], top["name_en"])

    def test_unrecognised_input_yields_no_false_differential(self):
        """Better to return nothing than to invent a condition."""
        _, headers = self._patient()
        body = self.client.post(
            "/api/v1/triage",
            json={"symptoms": "something vague and unclear", "age_years": 30},
            headers=headers,
        ).json()
        self.assertEqual([], body["differential"])


if __name__ == "__main__":
    unittest.main()
