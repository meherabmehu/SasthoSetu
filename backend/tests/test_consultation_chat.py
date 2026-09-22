# -*- coding: utf-8 -*-
"""Both sides of a consultation must be able to find it and talk in it.

The message endpoints existed from the start, but nothing listed a person's
consultations: the id was known only to whoever opened the encounter, so the
patient could never reach the thread at all. The chat was a room with one
door, on the doctor's side.

Covered here:

  - after a doctor opens a consultation, it appears in both parties' lists;
  - each side sees the other's name, not their own;
  - messages flow both ways and list in order;
  - a completed consultation refuses new messages;
  - an outsider is refused the list of someone else's thread - well, their
    own list, which is empty; the thread itself is guarded by the
    participant check that already existed.
"""
import os
import tempfile
import unittest
import uuid
from datetime import date, timedelta
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/chat.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.doctor import Doctor  # noqa: E402
from app.models.user import User  # noqa: E402

PASSWORD = "Passw0rd@123"


def _future(days):
    return (date.today() + timedelta(days=days)).isoformat()


class ConsultationChatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app, raise_server_exceptions=False)

    def _account(self, role="PATIENT", name="Test User"):
        email = f"{role.lower()}-{uuid.uuid4().hex[:8]}@example.com"
        self.client.post(
            "/api/v1/users",
            json={
                "full_name": name,
                "email": email,
                "phone": f"017{uuid.uuid4().int % 100000000:08d}",
                "password": PASSWORD,
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
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
        return user_id, {
            "Authorization": f"Bearer {login.json()['access_token']}"
        }

    def _patient(self, name="Rashida Patient"):
        user_id, headers = self._account("PATIENT", name)
        created = self.client.post(
            f"/api/v1/patients/{user_id}",
            json={
                "date_of_birth": "1995-04-12",
                "gender": "FEMALE",
                "blood_group": "O+",
                "height_cm": 160,
                "weight_kg": 55,
                "emergency_contact": "01712345678",
                "address": "Dhaka",
            },
            headers=headers,
        )
        self.assertIn(created.status_code, (200, 201), created.text)
        return user_id, headers

    def _verified_doctor(self, name="Kamal Doctor"):
        user_id, headers = self._account("DOCTOR", name)
        created = self.client.post(
            f"/api/v1/doctors/{user_id}",
            json={
                "bmdc_number": f"BMDC-{uuid.uuid4().hex[:8].upper()}",
                "specialization": "General Medicine",
                "experience_years": 10,
                "consultation_fee": 800.0,
                "hospital_name": "Test Hospital",
                "bio": "Test doctor",
            },
            headers=headers,
        )
        self.assertIn(created.status_code, (200, 201), created.text)
        session = SessionLocal()
        try:
            row = session.query(Doctor).filter(Doctor.user_id == user_id).first()
            row.verification_status = True
            session.commit()
            table_id = row.id
        finally:
            session.close()
        return user_id, table_id, headers

    def _consultation(self):
        """A booked appointment whose consultation the doctor has opened."""
        patient_user, patient_headers = self._patient()
        doctor_user, doctor_table, doctor_headers = self._verified_doctor()

        self.client.post(
            f"/api/v1/doctor-availability/{doctor_table}",
            json={
                "available_date": _future(2),
                "start_time": "10:00",
                "end_time": "11:00",
            },
            headers=doctor_headers,
        )
        booked = self.client.post(
            f"/api/v1/appointments/{patient_user}",
            json={
                "doctor_id": doctor_table,
                "appointment_date": _future(2),
                "appointment_time": "10:00",
                "reason": "persistent cough",
            },
            headers=patient_headers,
        )
        self.assertEqual(200, booked.status_code, booked.text)

        started = self.client.post(
            "/api/v1/consultations",
            json={"appointment_id": booked.json().get("appointment_id")
                  or booked.json().get("id")},
            headers=doctor_headers,
        )
        # The booking response shape varies; fall back to the doctor's list.
        if started.status_code != 200:
            appointments = self.client.get(
                f"/api/v1/appointments/doctor/{doctor_table}",
                headers=doctor_headers,
            ).json()
            appointment_id = appointments[0]["id"]
            started = self.client.post(
                "/api/v1/consultations",
                json={"appointment_id": appointment_id},
                headers=doctor_headers,
            )
        self.assertEqual(200, started.status_code, started.text)
        consultation_id = started.json()["id"]
        return consultation_id, patient_user, patient_headers, doctor_headers

    def test_both_sides_find_it_and_see_each_other(self):
        consultation_id, patient_user, patient_headers, doctor_headers = (
            self._consultation()
        )

        patient_list = self.client.get(
            "/api/v1/consultations/mine", headers=patient_headers
        )
        self.assertEqual(200, patient_list.status_code)
        patient_items = patient_list.json()
        self.assertEqual(1, len(patient_items))
        self.assertEqual(consultation_id, patient_items[0]["id"])
        self.assertEqual("Kamal Doctor", patient_items[0]["with"])

        doctor_list = self.client.get(
            "/api/v1/consultations/mine", headers=doctor_headers
        )
        self.assertEqual(200, doctor_list.status_code)
        doctor_items = doctor_list.json()
        self.assertEqual(1, len(doctor_items))
        self.assertEqual("Rashida Patient", doctor_items[0]["with"])

    def test_messages_flow_both_ways_in_order(self):
        consultation_id, patient_user, patient_headers, doctor_headers = (
            self._consultation()
        )

        self.assertEqual(
            200,
            self.client.post(
                f"/api/v1/consultations/{consultation_id}/messages",
                json={"body": "Doctor, my cough is worse at night."},
                headers=patient_headers,
            ).status_code,
        )
        self.assertEqual(
            200,
            self.client.post(
                f"/api/v1/consultations/{consultation_id}/messages",
                json={"body": "Any fever along with it?"},
                headers=doctor_headers,
            ).status_code,
        )

        thread = self.client.get(
            f"/api/v1/consultations/{consultation_id}/messages",
            headers=patient_headers,
        )
        self.assertEqual(200, thread.status_code)
        bodies = [m["body"] for m in thread.json()]
        self.assertEqual(
            ["Doctor, my cough is worse at night.", "Any fever along with it?"],
            bodies,
        )

    def test_a_completed_consultation_refuses_new_messages(self):
        consultation_id, patient_user, patient_headers, doctor_headers = (
            self._consultation()
        )
        self.client.patch(
            f"/api/v1/consultations/{consultation_id}",
            json={"diagnosis": "Acute bronchitis", "advice": "Rest and fluids"},
            headers=doctor_headers,
        )
        closed = self.client.post(
            f"/api/v1/consultations/{consultation_id}/close",
            headers=doctor_headers,
        )
        self.assertEqual(200, closed.status_code, closed.text)

        blocked = self.client.post(
            f"/api/v1/consultations/{consultation_id}/messages",
            json={"body": "one more question"},
            headers=patient_headers,
        )
        self.assertEqual(409, blocked.status_code)

    def test_a_person_with_no_part_has_no_list(self):
        _, outsider_headers = self._account("PATIENT", "Nobody")
        listed = self.client.get(
            "/api/v1/consultations/mine", headers=outsider_headers
        )
        self.assertEqual(200, listed.status_code)
        self.assertEqual([], listed.json())

    def test_the_list_requires_a_token(self):
        self.assertEqual(
            401, self.client.get("/api/v1/consultations/mine").status_code
        )


if __name__ == "__main__":
    unittest.main()
