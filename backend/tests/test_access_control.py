# -*- coding: utf-8 -*-
"""Every endpoint is either deliberately public or requires a token.

Two distinct concerns are covered here.

The first is confidentiality: several endpoints served patient prescriptions,
medical records, uploaded files and notifications to anyone holding a user id,
with no token at all. Those are the tests that matter most.

The second is the product decision that clinical features require an account,
with a deliberately small exemption list for the paths that must keep working
for someone who has no account and may be in an emergency.
"""
import os
import tempfile
import unittest
import uuid
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/access.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.user import User  # noqa: E402


class AccessTestCase(unittest.TestCase):
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
        return user_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


class HealthRecordConfidentialityTests(AccessTestCase):
    """No health record may be readable without authentication."""

    def test_patient_records_are_not_readable_anonymously(self):
        victim_id, _ = self._account("PATIENT")

        paths = [
            f"/api/v1/prescriptions/patient/{victim_id}",
            f"/api/v1/medical-records/patient/{victim_id}",
            f"/api/v1/patients/{victim_id}/history",
            f"/api/v1/files/{victim_id}",
            f"/api/v1/notifications/{victim_id}",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(401, self.client.get(path).status_code)

    def test_file_download_and_delete_require_a_token(self):
        self.assertEqual(
            401, self.client.get("/api/v1/files/download/any-id").status_code
        )
        self.assertEqual(401, self.client.delete("/api/v1/files/any-id").status_code)

    def test_one_patient_cannot_read_another_patients_records(self):
        victim_id, _ = self._account("PATIENT")
        _, attacker = self._account("PATIENT")

        for path in (
            f"/api/v1/prescriptions/patient/{victim_id}",
            f"/api/v1/patients/{victim_id}/history",
            f"/api/v1/notifications/{victim_id}",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    403, self.client.get(path, headers=attacker).status_code
                )

    def test_a_clinician_may_read_a_patient_record(self):
        """Restricting to the owner alone would break the consultation."""
        victim_id, victim = self._account("PATIENT")
        self.client.post(
            f"/api/v1/patients/{victim_id}",
            json={
                "date_of_birth": "1990-01-01",
                "gender": "FEMALE",
                "blood_group": "B+",
                "height_cm": 158.0,
                "weight_kg": 55.0,
                "emergency_contact": "01711111111",
                "address": "Dhaka",
            },
            headers=victim,
        )
        _, doctor = self._account("DOCTOR")
        response = self.client.get(
            f"/api/v1/prescriptions/patient/{victim_id}", headers=doctor
        )
        self.assertEqual(200, response.status_code)

    def test_a_clinician_may_not_read_a_patients_notifications(self):
        """Personal correspondence is not part of the clinical record."""
        victim_id, _ = self._account("PATIENT")
        _, doctor = self._account("DOCTOR")
        response = self.client.get(
            f"/api/v1/notifications/{victim_id}", headers=doctor
        )
        self.assertEqual(403, response.status_code)


class FeatureGatingTests(AccessTestCase):
    """Clinical features require an account."""

    GATED = [
        ("POST", "/api/v1/triage", {"symptoms": "জ্বর", "age_years": 30}),
        ("POST", "/api/v1/triage/sessions", {"symptoms": "জ্বর", "age_years": 30}),
        ("GET", "/api/v1/pharmacies/search?medicine=Napa", None),
        ("GET", "/api/v1/lab-tests", None),
        ("GET", "/api/v1/doctors", None),
        ("GET", "/api/v1/doctors/match", None),
        ("GET", "/api/v1/recommendations/doctors", None),
        ("GET", "/api/v1/hospitals", None),
        ("GET", "/api/v1/hospitals/nearby", None),
        ("GET", "/api/v1/providers", None),
    ]

    def test_gated_endpoints_reject_anonymous_callers(self):
        for method, path, body in self.GATED:
            with self.subTest(path=path):
                response = (
                    self.client.get(path)
                    if method == "GET"
                    else self.client.post(path, json=body)
                )
                self.assertEqual(401, response.status_code)

    def test_gated_endpoints_work_once_signed_in(self):
        _, headers = self._account("PATIENT")
        for method, path, body in self.GATED:
            with self.subTest(path=path):
                response = (
                    self.client.get(path, headers=headers)
                    if method == "GET"
                    else self.client.post(path, json=body, headers=headers)
                )
                self.assertNotIn(response.status_code, (401, 403))


class PublicSurfaceTests(AccessTestCase):
    """The exemptions, each for a reason worth stating."""

    def test_registration_and_login_stay_open(self):
        for path, body in [
            ("/api/v1/users", {
                "full_name": "New User",
                "email": f"new-{uuid.uuid4().hex[:8]}@example.com",
                "phone": f"017{uuid.uuid4().int % 100000000:08d}",
                "password": "Passw0rd@123",
            }),
            ("/api/v1/auth/login", {"email": "nobody@example.com", "password": "x"}),
        ]:
            with self.subTest(path=path):
                # Login may reject the credentials, but must not demand a token.
                response = self.client.post(path, json=body)
                self.assertNotEqual(
                    403, response.status_code, "must not require authentication"
                )

    def test_prescription_verification_stays_open(self):
        """A pharmacy counter checking a prescription is not a platform user."""
        response = self.client.post(
            "/api/v1/prescriptions/verify", json={"verification_code": "ABCD1234"}
        )
        self.assertEqual(200, response.status_code)

    def test_sms_and_ivr_stay_open(self):
        """Someone without a smartphone or an account can still get triaged."""
        sms = self.client.post(
            "/api/v1/rural/sms/triage", json={"text": "বুকে ব্যথা"}
        )
        self.assertEqual(200, sms.status_code)
        self.assertEqual(200, self.client.get("/api/v1/rural/ivr/menu").status_code)

    def test_health_check_stays_open(self):
        self.assertEqual(200, self.client.get("/health").status_code)


if __name__ == "__main__":
    unittest.main()
