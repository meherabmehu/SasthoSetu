# -*- coding: utf-8 -*-
"""End-to-end clinical workflow tests.

Covers the journey the platform exists to deliver: triage, doctor matching,
booking, consultation, signed prescription and pharmacy verification.
"""
import os
import tempfile
import unittest
import uuid
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/clinical.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.doctor import Doctor  # noqa: E402
from app.models.user import User  # noqa: E402


def unique_email(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def unique_phone():
    return f"017{uuid.uuid4().int % 100000000:08d}"


class ClinicalTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app, raise_server_exceptions=False)

    def _account(self, role="PATIENT"):
        email = unique_email(role.lower())
        password = "Passw0rd@123"
        created = self.client.post(
            "/api/v1/users",
            json={
                "full_name": f"Test {role}",
                "email": email,
                "phone": unique_phone(),
                "password": password,
            },
        )
        self.assertIn(created.status_code, (200, 201), created.text)

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
        self.assertEqual(200, login.status_code, login.text)
        return user_id, {"Authorization": f"Bearer {login.json()['access_token']}"}

    def _patient(self):
        user_id, headers = self._account("PATIENT")
        response = self.client.post(
            f"/api/v1/patients/{user_id}",
            json={
                "date_of_birth": "1990-01-01",
                "gender": "FEMALE",
                "blood_group": "B+",
                "height_cm": 158.0,
                "weight_kg": 55.0,
                "emergency_contact": unique_phone(),
                "address": "Dhaka",
            },
            headers=headers,
        )
        self.assertIn(response.status_code, (200, 201), response.text)
        return user_id, headers

    def _doctor(self, specialization="General Medicine"):
        user_id, headers = self._account("DOCTOR")
        response = self.client.post(
            f"/api/v1/doctors/{user_id}",
            json={
                "bmdc_number": f"BMDC-{uuid.uuid4().hex[:8].upper()}",
                "specialization": specialization,
                "experience_years": 10,
                "consultation_fee": 800.0,
                "hospital_name": "Test Hospital",
                "bio": "Test doctor",
            },
            headers=headers,
        )
        self.assertIn(response.status_code, (200, 201), response.text)

        session = SessionLocal()
        try:
            doctor = session.query(Doctor).filter(Doctor.user_id == user_id).first()
            doctor.verification_status = True
            session.commit()
            doctor_id = doctor.id
        finally:
            session.close()
        return user_id, doctor_id, headers

    def _booked_appointment(self, date_text="2026-09-10", time_text="10:00"):
        patient_user_id, patient_headers = self._patient()
        _, doctor_id, doctor_headers = self._doctor()

        self.client.post(
            f"/api/v1/doctor-availability/{doctor_id}",
            json={
                "available_date": date_text,
                "start_time": time_text,
                "end_time": "11:00",
            },
            headers=doctor_headers,
        )
        booking = self.client.post(
            f"/api/v1/appointments/{patient_user_id}",
            json={
                "doctor_id": doctor_id,
                "appointment_date": date_text,
                "appointment_time": time_text,
                "reason": "Fever and cough for three days",
            },
            headers=patient_headers,
        )
        self.assertEqual(200, booking.status_code, booking.text)

        appointments = self.client.get(
            f"/api/v1/appointments/patient/{patient_user_id}", headers=patient_headers
        ).json()
        return {
            "appointment_id": appointments[0]["id"],
            "patient_user_id": patient_user_id,
            "patient_headers": patient_headers,
            "doctor_id": doctor_id,
            "doctor_headers": doctor_headers,
        }


class TriageSessionTests(ClinicalTestCase):
    def test_anonymous_triage_is_allowed(self):
        response = self.client.post(
            "/api/v1/triage/sessions",
            json={"symptoms": "তিন দিন ধরে জ্বর ও কাশি", "age_years": 30},
        )
        self.assertEqual(200, response.status_code, response.text)
        self.assertIn("triage_session_id", response.json())

    def test_emergency_triage_is_stored_with_flag(self):
        response = self.client.post(
            "/api/v1/triage/sessions",
            json={"symptoms": "বুকে ব্যথা, শ্বাস নিতে কষ্ট", "age_years": 55},
        )
        body = response.json()
        self.assertEqual("EMERGENCY", body["triage_level"])
        self.assertTrue(body["safety_flags"])

    def test_session_is_retrievable_by_its_owner(self):
        _, headers = self._patient()
        created = self.client.post(
            "/api/v1/triage/sessions",
            json={"symptoms": "মাথা ব্যথা", "age_years": 25},
            headers=headers,
        ).json()

        fetched = self.client.get(
            f"/api/v1/triage/sessions/{created['triage_session_id']}", headers=headers
        )
        self.assertEqual(200, fetched.status_code)

    def test_other_patients_cannot_read_a_session(self):
        _, owner = self._patient()
        created = self.client.post(
            "/api/v1/triage/sessions",
            json={"symptoms": "মাথা ব্যথা", "age_years": 25},
            headers=owner,
        ).json()

        _, intruder = self._patient()
        response = self.client.get(
            f"/api/v1/triage/sessions/{created['triage_session_id']}", headers=intruder
        )
        self.assertEqual(403, response.status_code)

    def test_history_lists_own_sessions(self):
        _, headers = self._patient()
        for _ in range(2):
            self.client.post(
                "/api/v1/triage/sessions",
                json={"symptoms": "জ্বর", "age_years": 30},
                headers=headers,
            )
        listing = self.client.get("/api/v1/triage/sessions/mine", headers=headers)
        self.assertEqual(200, listing.status_code)
        self.assertGreaterEqual(listing.json()["total"], 2)

    def test_clinician_can_override_and_flag_is_recorded(self):
        _, patient_headers = self._patient()
        created = self.client.post(
            "/api/v1/triage/sessions",
            json={"symptoms": "জ্বর", "age_years": 30},
            headers=patient_headers,
        ).json()

        _, _, doctor_headers = self._doctor()
        review = self.client.post(
            f"/api/v1/triage/sessions/{created['triage_session_id']}/review",
            json={"clinician_level": 5, "note": "Patient looked septic"},
            headers=doctor_headers,
        )
        self.assertEqual(200, review.status_code, review.text)
        self.assertTrue(review.json()["was_overridden"])
        self.assertEqual(5, review.json()["clinician_level"])

    def test_patient_cannot_review_triage(self):
        _, headers = self._patient()
        created = self.client.post(
            "/api/v1/triage/sessions",
            json={"symptoms": "জ্বর", "age_years": 30},
            headers=headers,
        ).json()
        response = self.client.post(
            f"/api/v1/triage/sessions/{created['triage_session_id']}/review",
            json={"clinician_level": 1},
            headers=headers,
        )
        self.assertEqual(403, response.status_code)


class DoctorMatchingTests(ClinicalTestCase):
    def test_match_returns_doctors_for_a_triage_session(self):
        self._doctor("Pulmonology")
        session = self.client.post(
            "/api/v1/triage/sessions",
            json={"symptoms": "কাশি ও জ্বর তিন দিন", "age_years": 30},
        ).json()

        matches = self.client.get(
            f"/api/v1/doctors/match?triage_session_id={session['triage_session_id']}"
        )
        self.assertEqual(200, matches.status_code)
        self.assertTrue(matches.json())

    def test_unverified_doctors_are_never_matched(self):
        user_id, headers = self._account("DOCTOR")
        self.client.post(
            f"/api/v1/doctors/{user_id}",
            json={
                "bmdc_number": f"BMDC-{uuid.uuid4().hex[:8].upper()}",
                "specialization": "Cardiology",
                "experience_years": 5,
                "consultation_fee": 1000.0,
                "hospital_name": "Unverified Clinic",
                "bio": "Pending verification",
            },
            headers=headers,
        )
        matches = self.client.get("/api/v1/doctors/match?specialty=Cardiology").json()
        session = SessionLocal()
        try:
            doctor = session.query(Doctor).filter(Doctor.user_id == user_id).first()
            unverified_id = doctor.id
        finally:
            session.close()
        self.assertNotIn(unverified_id, [m["doctor_id"] for m in matches])

    def test_fee_filter_is_applied(self):
        self._doctor("Dermatology")
        matches = self.client.get(
            "/api/v1/doctors/match?specialty=Dermatology&max_fee=100"
        ).json()
        self.assertTrue(all(m["consultation_fee"] <= 100 for m in matches))


class ConsultationTests(ClinicalTestCase):
    def test_doctor_can_run_and_close_a_consultation(self):
        context = self._booked_appointment("2026-09-11")
        started = self.client.post(
            "/api/v1/consultations",
            json={"appointment_id": context["appointment_id"]},
            headers=context["doctor_headers"],
        )
        self.assertEqual(200, started.status_code, started.text)
        consultation_id = started.json()["id"]

        updated = self.client.patch(
            f"/api/v1/consultations/{consultation_id}",
            json={"diagnosis": "Acute bronchitis", "advice": "Rest and fluids"},
            headers=context["doctor_headers"],
        )
        self.assertEqual(200, updated.status_code)

        closed = self.client.post(
            f"/api/v1/consultations/{consultation_id}/close",
            headers=context["doctor_headers"],
        )
        self.assertEqual(200, closed.status_code)
        self.assertTrue(closed.json()["is_signed"])

    def test_closing_without_a_diagnosis_is_rejected(self):
        context = self._booked_appointment("2026-09-12")
        consultation_id = self.client.post(
            "/api/v1/consultations",
            json={"appointment_id": context["appointment_id"]},
            headers=context["doctor_headers"],
        ).json()["id"]

        response = self.client.post(
            f"/api/v1/consultations/{consultation_id}/close",
            headers=context["doctor_headers"],
        )
        self.assertEqual(400, response.status_code)

    def test_signed_consultation_cannot_be_edited(self):
        context = self._booked_appointment("2026-09-13")
        consultation_id = self.client.post(
            "/api/v1/consultations",
            json={"appointment_id": context["appointment_id"]},
            headers=context["doctor_headers"],
        ).json()["id"]
        self.client.patch(
            f"/api/v1/consultations/{consultation_id}",
            json={"diagnosis": "Migraine"},
            headers=context["doctor_headers"],
        )
        self.client.post(
            f"/api/v1/consultations/{consultation_id}/close",
            headers=context["doctor_headers"],
        )

        response = self.client.patch(
            f"/api/v1/consultations/{consultation_id}",
            json={"diagnosis": "Changed my mind"},
            headers=context["doctor_headers"],
        )
        self.assertEqual(409, response.status_code)

    def test_outsider_cannot_read_a_consultation(self):
        context = self._booked_appointment("2026-09-14")
        consultation_id = self.client.post(
            "/api/v1/consultations",
            json={"appointment_id": context["appointment_id"]},
            headers=context["doctor_headers"],
        ).json()["id"]

        _, intruder = self._patient()
        response = self.client.get(
            f"/api/v1/consultations/{consultation_id}", headers=intruder
        )
        self.assertEqual(403, response.status_code)

    def test_participants_can_exchange_messages(self):
        context = self._booked_appointment("2026-09-15")
        consultation_id = self.client.post(
            "/api/v1/consultations",
            json={"appointment_id": context["appointment_id"]},
            headers=context["doctor_headers"],
        ).json()["id"]

        self.client.post(
            f"/api/v1/consultations/{consultation_id}/messages",
            json={"body": "কেমন লাগছে এখন?"},
            headers=context["doctor_headers"],
        )
        self.client.post(
            f"/api/v1/consultations/{consultation_id}/messages",
            json={"body": "একটু ভালো লাগছে"},
            headers=context["patient_headers"],
        )

        messages = self.client.get(
            f"/api/v1/consultations/{consultation_id}/messages",
            headers=context["patient_headers"],
        ).json()
        self.assertEqual(2, len(messages))
        self.assertEqual(["DOCTOR", "PATIENT"], [m["sender_role"] for m in messages])


class PrescriptionTests(ClinicalTestCase):
    def _issue(self, items=None, date_text="2026-09-20"):
        context = self._booked_appointment(date_text)
        consultation_id = self.client.post(
            "/api/v1/consultations",
            json={"appointment_id": context["appointment_id"]},
            headers=context["doctor_headers"],
        ).json()["id"]
        self.client.patch(
            f"/api/v1/consultations/{consultation_id}",
            json={"diagnosis": "Acute bronchitis"},
            headers=context["doctor_headers"],
        )
        response = self.client.post(
            "/api/v1/prescriptions/issue",
            json={
                "consultation_id": consultation_id,
                "items": items
                or [
                    {
                        "medicine_name": "Napa 500",
                        "frequency": "1+1+1",
                        "duration": "5 days",
                    }
                ],
            },
            headers=context["doctor_headers"],
        )
        self.assertEqual(200, response.status_code, response.text)
        return response.json(), context

    def test_issued_prescription_verifies_successfully(self):
        prescription, _ = self._issue()
        verification = self.client.post(
            "/api/v1/prescriptions/verify",
            json={"verification_code": prescription["verification_code"]},
        ).json()
        self.assertTrue(verification["is_valid"], verification["reason"])
        self.assertTrue(verification["signature_valid"])

    def test_unknown_code_is_rejected(self):
        verification = self.client.post(
            "/api/v1/prescriptions/verify",
            json={"verification_code": "NOTAREALCODE"},
        ).json()
        self.assertFalse(verification["is_valid"])

    def test_dispensing_is_single_use(self):
        prescription, context = self._issue(date_text="2026-09-21")
        code = prescription["verification_code"]

        first = self.client.post(
            "/api/v1/prescriptions/dispense",
            json={"verification_code": code},
            headers=context["doctor_headers"],
        )
        self.assertEqual(200, first.status_code, first.text)

        second = self.client.post(
            "/api/v1/prescriptions/dispense",
            json={"verification_code": code},
            headers=context["doctor_headers"],
        )
        self.assertEqual(409, second.status_code)

        after = self.client.post(
            "/api/v1/prescriptions/verify", json={"verification_code": code}
        ).json()
        self.assertFalse(after["is_valid"])
        self.assertTrue(after["already_dispensed"])

    def test_tampering_with_an_item_invalidates_the_signature(self):
        prescription, _ = self._issue(date_text="2026-09-22")

        from app.models.prescription_item import PrescriptionLine

        session = SessionLocal()
        try:
            line = (
                session.query(PrescriptionLine)
                .filter(PrescriptionLine.prescription_id == prescription["id"])
                .first()
            )
            line.medicine_name = "Morphine"
            session.commit()
        finally:
            session.close()

        verification = self.client.post(
            "/api/v1/prescriptions/verify",
            json={"verification_code": prescription["verification_code"]},
        ).json()
        self.assertFalse(verification["is_valid"])
        self.assertFalse(verification["signature_valid"])

    def test_interactions_are_screened_at_issue_time(self):
        prescription, _ = self._issue(
            items=[
                {"medicine_name": "Warfin", "frequency": "0+0+1", "duration": "10 days"},
                {
                    "medicine_name": "Ecosprin 75",
                    "frequency": "1+0+0",
                    "duration": "10 days",
                },
            ],
            date_text="2026-09-23",
        )
        report = prescription["interaction_report"]
        self.assertEqual("major", report["highest_severity"])

    def test_generic_name_is_resolved_for_each_item(self):
        prescription, _ = self._issue(date_text="2026-09-24")
        self.assertEqual("paracetamol", prescription["items"][0]["generic_name"])

    def test_cancelled_prescription_cannot_be_dispensed(self):
        prescription, context = self._issue(date_text="2026-09-25")
        self.client.post(
            f"/api/v1/prescriptions/{prescription['id']}/cancel",
            headers=context["doctor_headers"],
        )
        verification = self.client.post(
            "/api/v1/prescriptions/verify",
            json={"verification_code": prescription["verification_code"]},
        ).json()
        self.assertFalse(verification["is_valid"])
        self.assertTrue(verification["is_cancelled"])

    def test_patient_can_list_their_prescriptions(self):
        prescription, context = self._issue(date_text="2026-09-26")
        listing = self.client.get(
            f"/api/v1/prescriptions/records/{context['patient_user_id']}",
            headers=context["patient_headers"],
        )
        self.assertEqual(200, listing.status_code)
        codes = [p["verification_code"] for p in listing.json()]
        self.assertIn(prescription["verification_code"], codes)

    def test_other_patients_cannot_list_prescriptions(self):
        _, context = self._issue(date_text="2026-09-27")
        _, intruder = self._patient()
        response = self.client.get(
            f"/api/v1/prescriptions/records/{context['patient_user_id']}",
            headers=intruder,
        )
        self.assertEqual(403, response.status_code)


class AppointmentIntegrityTests(ClinicalTestCase):
    def test_slot_cannot_be_double_booked(self):
        context = self._booked_appointment("2026-10-01", "09:00")

        _, second_patient_headers = self._patient()
        session = SessionLocal()
        try:
            other_user = (
                session.query(User)
                .filter(User.role == "PATIENT")
                .order_by(User.id.desc())
                .first()
            )
            other_user_id = other_user.id
        finally:
            session.close()

        response = self.client.post(
            f"/api/v1/appointments/{other_user_id}",
            json={
                "doctor_id": context["doctor_id"],
                "appointment_date": "2026-10-01",
                "appointment_time": "09:00",
                "reason": "Another patient wants the same slot",
            },
            headers=second_patient_headers,
        )
        self.assertIn(response.status_code, (400, 409))


if __name__ == "__main__":
    unittest.main()
