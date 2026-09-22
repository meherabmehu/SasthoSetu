# -*- coding: utf-8 -*-
"""Clinician self-registration.

A clinician used to need an administrator to create their account, because
registration always produced a patient. The main login page now offers a
clinician door with its own sign-up form, and this is what it hits.

The flow only works if the safety property survives it: a self-registered
doctor is unverified, invisible to patients, and cannot open consultations,
until an administrator checks the BMDC number. Registration must never
short-circuit that.
"""
import os
import tempfile
import unittest
import uuid
from datetime import date, timedelta
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/docreg.db"
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


def _doctor_payload():
    return {
        "full_name": "Self Registered",
        "email": f"doc-{uuid.uuid4().hex[:8]}@example.com",
        "phone": f"017{uuid.uuid4().int % 100000000:08d}",
        "password": PASSWORD,
        "bmdc_number": f"BMDC-{uuid.uuid4().hex[:8].upper()}",
        "specialization": "Medicine",
        "hospital_name": "Upazila Health Complex",
    }


class DoctorRegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app, raise_server_exceptions=False)

    def _admin(self):
        email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
        self.client.post(
            "/api/v1/users",
            json={
                "full_name": "Site Admin",
                "email": email,
                "phone": f"018{uuid.uuid4().int % 100000000:08d}",
                "password": PASSWORD,
            },
        )
        session = SessionLocal()
        try:
            user = session.query(User).filter(User.email == email).first()
            user.role = "ADMIN"
            session.commit()
        finally:
            session.close()
        login = self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def test_registration_creates_an_unverified_doctor(self):
        payload = _doctor_payload()
        created = self.client.post("/api/v1/auth/register-doctor", json=payload)
        self.assertEqual(200, created.status_code, created.text)

        login = self.client.post(
            "/api/v1/auth/login",
            json={"email": payload["email"], "password": PASSWORD},
        )
        self.assertEqual(200, login.status_code)
        token = {"Authorization": f"Bearer {login.json()['access_token']}"}

        me = self.client.get("/api/v1/auth/me", headers=token).json()
        self.assertEqual("DOCTOR", me["role"])

        profile = self.client.get("/api/v1/doctors/me", headers=token).json()
        self.assertEqual(payload["bmdc_number"], profile["bmdc_number"])
        self.assertFalse(profile["verification_status"])

        # Both rows exist and are linked: no half-created account.
        session = SessionLocal()
        try:
            user = session.query(User).filter(User.email == payload["email"]).first()
            doctor = (
                session.query(Doctor).filter(Doctor.user_id == user.id).first()
            )
            self.assertIsNotNone(doctor)
        finally:
            session.close()

    def test_a_duplicate_email_is_a_clear_409(self):
        payload = _doctor_payload()
        self.client.post("/api/v1/auth/register-doctor", json=payload)
        again = _doctor_payload()
        again["email"] = payload["email"]
        again["phone"] = payload["phone"]  # different person, same address
        response = self.client.post("/api/v1/auth/register-doctor", json=again)
        self.assertEqual(409, response.status_code)
        self.assertIn("email", response.json()["detail"].lower())

    def test_an_unverified_doctor_is_not_offered_to_patients(self):
        payload = _doctor_payload()
        self.client.post("/api/v1/auth/register-doctor", json=payload)
        listing = self.client.get(
            "/api/v1/doctors/specialization/Medicine"
        )
        if listing.status_code == 200:
            listed = listing.json()
            items = listed if isinstance(listed, list) else listed.get("items", [])
            self.assertFalse(
                any(d.get("bmdc_number") == payload["bmdc_number"] for d in items)
            )

        # And appears in the administrator's pending queue.
        admin = self._admin()
        pending = self.client.get("/api/v1/doctors/pending", headers=admin)
        self.assertEqual(200, pending.status_code)
        queued = pending.json()
        items = queued if isinstance(queued, list) else queued.get("items", [])
        self.assertTrue(
            any(d.get("bmdc_number") == payload["bmdc_number"] for d in items)
        )

    def test_a_short_password_is_refused(self):
        payload = _doctor_payload()
        payload["password"] = "short"
        self.assertEqual(
            422,
            self.client.post(
                "/api/v1/auth/register-doctor", json=payload
            ).status_code,
        )

    def test_patient_registration_still_makes_a_patient(self):
        email = f"pat-{uuid.uuid4().hex[:8]}@example.com"
        created = self.client.post(
            "/api/v1/users",
            json={
                "full_name": "Ordinary Patient",
                "email": email,
                "phone": f"019{uuid.uuid4().int % 100000000:08d}",
                "password": PASSWORD,
            },
        )
        self.assertEqual(200, created.status_code)
        session = SessionLocal()
        try:
            user = session.query(User).filter(User.email == email).first()
            self.assertEqual("PATIENT", user.role)
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
