"""Cross-account and replay regressions against an isolated database."""
import os
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.account_token import AccountToken
from app.models.appointment import Appointment
from app.models.base import Base
from app.models.doctor import Doctor
from app.models.file_record import FileRecord
from app.models.patient import Patient
from app.models.user import User
from app.modules.auth import tokens


class SecurityRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password("OldPassword123!")

    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        for name, role in [("patient", "PATIENT"), ("other", "PATIENT"),
                           ("doctor", "DOCTOR"), ("stranger", "DOCTOR"), ("admin", "ADMIN")]:
            self.db.add(User(id=name, full_name=name, email=f"{name}@example.com", phone=name,
                             password_hash=self.password_hash, role=role))
        self.db.flush()
        self.db.add(Patient(id="p", user_id="patient", date_of_birth=date(1990, 1, 1),
                            gender="FEMALE", blood_group="B+", height_cm=160, weight_kg=60,
                            emergency_contact="01711111111", address="Dhaka"))
        for name in ["doctor", "stranger"]:
            self.db.add(Doctor(id=name, user_id=name, bmdc_number=name, specialization="Medicine",
                               experience_years=5, consultation_fee=600, hospital_name="Test",
                               verification_status=True))
        self.db.flush()
        self.db.add(Appointment(id="a", patient_id="p", doctor_id="doctor", status="CONFIRMED",
                                appointment_date="2099-01-01", appointment_time="10:00", reason="Fever"))
        self.db.add(FileRecord(id="file", patient_id="p", uploaded_by="patient", file_name="a.pdf",
                               file_type="application/pdf", content=b"%PDF-demo", file_size=9))
        self.db.commit()
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app, raise_server_exceptions=True)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def headers(self, name):
        user = self.db.get(User, name)
        return {"Authorization": "Bearer " + create_access_token(
            {"sub": name, "ver": user.token_version})}

    def grant(self):
        return self.client.put("/api/v1/patients/me/care-access/doctor", json={"granted": True},
                               headers=self.headers("patient"))

    def test_doctor_needs_patient_consent_and_relationship(self):
        for name in ["doctor", "stranger"]:
            response = self.client.get("/api/v1/files/download/file", headers=self.headers(name))
            self.assertEqual(403, response.status_code)
        self.assertEqual(200, self.grant().status_code)
        self.assertEqual(200, self.client.get("/api/v1/files/download/file",
                                             headers=self.headers("doctor")).status_code)
        self.assertEqual(403, self.client.get("/api/v1/files/download/file",
                                             headers=self.headers("stranger")).status_code)

    def test_revocation_takes_effect_immediately(self):
        self.grant()
        self.client.put("/api/v1/patients/me/care-access/doctor", json={"granted": False},
                         headers=self.headers("patient"))
        self.assertEqual(403, self.client.get("/api/v1/prescriptions/patient/patient",
                                             headers=self.headers("doctor")).status_code)

    def test_unverified_doctor_cannot_use_old_consent(self):
        self.grant()
        self.db.get(Doctor, "doctor").verification_status = False
        self.db.commit()
        self.assertEqual(403, self.client.get("/api/v1/files/patient",
                                             headers=self.headers("doctor")).status_code)

    def test_patient_cannot_grant_access_to_an_unrelated_doctor(self):
        response = self.client.put("/api/v1/patients/me/care-access/stranger",
                                    json={"granted": True}, headers=self.headers("patient"))
        self.assertEqual(403, response.status_code)

    def test_doctor_cannot_impersonate_another_doctor(self):
        for path in ["medical-records", "prescriptions", "appointments"]:
            response = self.client.get(f"/api/v1/{path}/doctor/doctor",
                                        headers=self.headers("stranger"))
            self.assertEqual(403, response.status_code, path)
        response = self.client.post("/api/v1/medical-records/doctor", json={
            "patient_id": "p", "diagnosis": "test", "notes": "test", "record_date": "2026-11-03"
        }, headers=self.headers("stranger"))
        self.assertEqual(403, response.status_code)

    def test_fhir_requires_the_same_consent(self):
        self.assertEqual(403, self.client.get("/api/v1/fhir/Patient/p",
                                             headers=self.headers("doctor")).status_code)
        self.grant()
        self.assertEqual(200, self.client.get("/api/v1/fhir/Patient/p",
                                             headers=self.headers("doctor")).status_code)

    def test_reset_link_is_single_use_and_revokes_old_sessions(self):
        old_headers = self.headers("patient")
        raw = tokens.issue(self.db.get(User, "patient"), "reset", self.db)
        self.db.commit()
        body = {"token": raw, "new_password": "Replacement123!"}
        self.assertEqual(200, self.client.post("/api/v1/auth/reset-password", json=body).status_code)
        self.assertEqual(400, self.client.post("/api/v1/auth/reset-password", json=body).status_code)
        self.assertEqual(401, self.client.get("/api/v1/auth/me", headers=old_headers).status_code)
        self.assertIsNone(self.db.query(AccountToken).filter(AccountToken.token_hash == raw).first())

    def test_expired_reset_is_rejected(self):
        raw = tokens.issue(self.db.get(User, "patient"), "reset", self.db)
        self.db.flush()
        self.db.query(AccountToken).update({"expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)})
        self.db.commit()
        self.assertEqual(400, self.client.post("/api/v1/auth/reset-password", json={
            "token": raw, "new_password": "Replacement123!"}).status_code)

    def test_refresh_rotates_and_logout_revokes_both_credentials(self):
        raw = tokens.issue(self.db.get(User, "patient"), "refresh", self.db)
        self.db.commit()
        result = self.client.post("/api/v1/auth/refresh", json={"token": raw})
        self.assertEqual(200, result.status_code)
        self.assertEqual(400, self.client.post("/api/v1/auth/refresh", json={"token": raw}).status_code)
        headers = {"Authorization": "Bearer " + result.json()["access_token"]}
        self.assertEqual(200, self.client.post("/api/v1/auth/logout", headers=headers).status_code)
        self.assertEqual(401, self.client.get("/api/v1/auth/me", headers=headers).status_code)
        self.assertEqual(400, self.client.post("/api/v1/auth/refresh", json={
            "token": result.json()["refresh_token"]}).status_code)

    def test_password_change_revokes_old_session(self):
        headers = self.headers("patient")
        self.assertEqual(200, self.client.post("/api/v1/auth/change-password", headers=headers,
            json={"current_password": "OldPassword123!", "new_password": "Replacement123!"}).status_code)
        self.assertEqual(401, self.client.get("/api/v1/auth/me", headers=headers).status_code)

    def test_demo_outbox_is_admin_only_and_does_not_send_mail(self):
        with patch.dict(os.environ, {"ACCOUNT_EMAIL_MODE": "demo"}), patch.object(tokens, "deliver_link") as send:
            result = self.client.post("/api/v1/auth/forgot-password", json={"email": "patient@example.com"})
            unknown = self.client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
            self.assertEqual(result.json(), unknown.json())
            send.assert_not_called()
            self.assertEqual(403, self.client.get("/api/v1/auth/demo-outbox",
                                                 headers=self.headers("patient")).status_code)
            response = self.client.get("/api/v1/auth/demo-outbox", headers=self.headers("admin"))
            self.assertEqual(200, response.status_code)
            self.assertTrue(response.json()["messages"])

    def checkout(self, name="patient", key="test-payment-key"):
        return self.client.post("/api/v1/payments/checkout", headers=self.headers(name), json={
            "purpose": "CONSULTATION", "method": "bkash", "idempotency_key": key,
            "appointment_id": "a"})

    def test_payment_ownership_and_idempotency_do_not_leak(self):
        payment = self.checkout().json()
        self.assertTrue(payment["is_sandbox"])
        self.assertEqual(403, self.checkout("other").status_code)
        self.assertEqual(403, self.checkout("other", "another-payment-key").status_code)
        self.assertEqual(payment["id"], self.checkout().json()["id"])
        self.assertEqual(403, self.client.post(f"/api/v1/payments/{payment['id']}/simulate",
            headers=self.headers("other"), json={"status": "COMPLETED"}).status_code)

    def test_simulation_completes_once_without_provider_calls(self):
        payment = self.checkout().json()
        for _ in range(2):
            result = self.client.post(f"/api/v1/payments/{payment['id']}/simulate",
                headers=self.headers("patient"), json={"status": "COMPLETED"})
            self.assertEqual("COMPLETED", result.json()["status"])
            self.assertTrue(result.json()["is_sandbox"])

    def test_configured_gateway_credentials_never_enable_live_mode(self):
        from app.payments.gateways import ChargeRequest, get_gateway
        gateway = get_gateway("bkash")
        with patch.object(gateway, "is_configured", return_value=True):
            self.assertTrue(gateway.initiate(ChargeRequest("demo", 100)).is_sandbox)
            self.assertTrue(gateway.refund("demo", 100).is_sandbox)

    def test_readiness_detects_an_unmigrated_database(self):
        with patch("app.core.readiness.engine", self.engine):
            response = self.client.get("/ready")
            self.assertEqual(200, response.status_code, response.text)
            AccountToken.__table__.drop(self.engine)
            response = self.client.get("/ready")
            self.assertEqual(503, response.status_code)
            self.assertFalse(response.json()["checks"]["database"])

    def test_shared_limit_counts_across_independent_sessions(self):
        from app.core.shared_limits import check_database_limit
        sessions = sessionmaker(bind=self.engine)
        self.assertEqual(0, check_database_limit("client", 1, sessions, timestamp=600))
        self.assertEqual(59, check_database_limit("client", 1, sessions, timestamp=601))
        self.assertEqual(0, check_database_limit("client", 1, sessions, timestamp=660))

    def test_private_api_responses_disable_browser_caching(self):
        result = self.client.get("/api/v1/auth/me", headers=self.headers("patient"))
        self.assertEqual(200, result.status_code)
        self.assertEqual("no-store", result.headers.get("cache-control"))

    def test_checkout_rejects_conflicting_targets(self):
        result = self.client.post("/api/v1/payments/checkout", headers=self.headers("patient"),
            json={"purpose": "CONSULTATION", "method": "bkash", "idempotency_key": "mixed-target-key",
                  "appointment_id": "a", "lab_order_id": "another-patient-order"})
        self.assertEqual(400, result.status_code)


if __name__ == "__main__":
    unittest.main()
