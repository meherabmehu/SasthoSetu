# -*- coding: utf-8 -*-
"""Notifications have to be readable, not just recordable.

Plenty of the application already writes notifications - a booked
appointment, an issued prescription, a payment - but until the notifications
page existed there was no way to read any of them, so the table filled up
with messages nobody would ever see.

What has to hold:

  - a booking produces a notification for the patient who booked;
  - the list is newest first, and carries a timestamp to order by;
  - marking read works only for the recipient;
  - a stranger cannot read someone else's notifications.
"""
import os
import tempfile
import unittest
import uuid
from datetime import date, timedelta
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/notif.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.user import User  # noqa: E402


def _future(days):
    return (date.today() + timedelta(days=days)).isoformat()


class NotificationFlowTests(unittest.TestCase):
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
                "full_name": f"Test {role}",
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
        return user_id, {
            "Authorization": f"Bearer {login.json()['access_token']}"
        }

    def _bookable_doctor(self):
        """A verified doctor with a free slot in the coming week."""
        doctor_id, doctor_headers = self._account("DOCTOR")
        created = self.client.post(
            f"/api/v1/doctors/{doctor_id}",
            json={
                "bmdc_number": f"BMDC-{uuid.uuid4().hex[:8].upper()}",
                "specialization": "General Medicine",
                "experience_years": 10,
                "consultation_fee": 800.0,
                "hospital_name": "Dhaka Medical College",
                "bio": "Test doctor",
            },
            headers=doctor_headers,
        )
        self.assertIn(created.status_code, (200, 201), created.text)
        session = SessionLocal()
        try:
            from app.models.doctor import Doctor
            row = session.query(Doctor).filter(Doctor.user_id == doctor_id).first()
            row.verification_status = True
            session.commit()
            table_id = row.id
        finally:
            session.close()

        self.client.post(
            f"/api/v1/doctor-availability/{table_id}",
            json={
                "available_date": _future(2),
                "start_time": "10:00",
                "end_time": "11:00",
            },
            headers=doctor_headers,
        )
        return table_id, doctor_headers

    def test_booking_notifies_the_patient(self):
        patient_id, patient = self._account()
        doctor_id, _ = self._bookable_doctor()

        self.client.post(
            f"/api/v1/patients/{patient_id}",
            json={
                "date_of_birth": "1995-04-12",
                "gender": "FEMALE",
                "blood_group": "O+",
                "height_cm": 160,
                "weight_kg": 55,
                "emergency_contact": "01712345678",
                "address": "Dhaka",
            },
            headers=patient,
        )
        booked = self.client.post(
            f"/api/v1/appointments/{patient_id}",
            json={
                "doctor_id": doctor_id,
                "appointment_date": _future(2),
                "appointment_time": "10:00",
                "reason": "fever",
            },
            headers=patient,
        )
        self.assertEqual(200, booked.status_code, booked.text)

        listed = self.client.get(
            f"/api/v1/notifications/{patient_id}", headers=patient
        )
        self.assertEqual(200, listed.status_code)
        items = listed.json()
        self.assertTrue(any("booked" in n["message"] for n in items))
        # The list carries the timestamp the page orders by.
        self.assertTrue(all(n.get("created_at") for n in items))

    def test_the_list_is_newest_first(self):
        user_id, headers = self._account()
        from app.modules.notifications.service import create_notification

        session = SessionLocal()
        try:
            create_notification(user_id, "Old", "first", db=session)
            create_notification(user_id, "New", "second", db=session)
        finally:
            session.close()

        listed = self.client.get(
            f"/api/v1/notifications/{user_id}", headers=headers
        ).json()
        titles = [n["title"] for n in listed]
        self.assertLess(titles.index("New"), titles.index("Old"))

    def test_marking_read_is_for_the_recipient_only(self):
        user_id, headers = self._account()
        from app.modules.notifications.service import create_notification

        session = SessionLocal()
        try:
            create_notification(user_id, "Mine", "hello", db=session)
        finally:
            session.close()
        notification_id = self.client.get(
            f"/api/v1/notifications/{user_id}", headers=headers
        ).json()[0]["id"]

        _, stranger = self._account()
        self.assertEqual(
            403,
            self.client.patch(
                f"/api/v1/notifications/{notification_id}/read",
                json={},
                headers=stranger,
            ).status_code,
        )
        # Still unread.
        still = self.client.get(
            f"/api/v1/notifications/{user_id}", headers=headers
        ).json()
        self.assertFalse(still[0]["is_read"])

        self.assertEqual(
            200,
            self.client.patch(
                f"/api/v1/notifications/{notification_id}/read",
                json={},
                headers=headers,
            ).status_code,
        )
        after = self.client.get(
            f"/api/v1/notifications/{user_id}", headers=headers
        ).json()
        self.assertTrue(after[0]["is_read"])

    def test_a_stranger_cannot_read_someone_elses_notifications(self):
        victim_id, _ = self._account()
        _, attacker = self._account()
        self.assertEqual(
            403,
            self.client.get(
                f"/api/v1/notifications/{victim_id}", headers=attacker
            ).status_code,
        )


if __name__ == "__main__":
    unittest.main()
