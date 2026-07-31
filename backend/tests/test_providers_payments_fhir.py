# -*- coding: utf-8 -*-
"""Lab, pharmacy, payment and FHIR interoperability tests."""
import os
import tempfile
import unittest
import uuid
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/providers.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.doctor import Doctor  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.models.user import User  # noqa: E402
from app.payments.gateways import get_gateway  # noqa: E402


def unique_email(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def unique_phone():
    return f"017{uuid.uuid4().int % 100000000:08d}"


class ProviderTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app, raise_server_exceptions=False)

    def _account(self, role="PATIENT"):
        email = unique_email(role.lower())
        password = "Passw0rd@123"
        self.client.post(
            "/api/v1/users",
            json={
                "full_name": f"Test {role}",
                "email": email,
                "phone": unique_phone(),
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
                "date_of_birth": "1990-05-05",
                "gender": "FEMALE",
                "blood_group": "O+",
                "height_cm": 160.0,
                "weight_kg": 60.0,
                "emergency_contact": unique_phone(),
                "address": "Dhaka",
            },
            headers=headers,
        )
        session = SessionLocal()
        try:
            patient_id = (
                session.query(Patient).filter(Patient.user_id == user_id).first().id
            )
        finally:
            session.close()
        return user_id, patient_id, headers

    def _doctor(self):
        user_id, headers = self._account("DOCTOR")
        self.client.post(
            f"/api/v1/doctors/{user_id}",
            json={
                "bmdc_number": f"BMDC-{uuid.uuid4().hex[:8].upper()}",
                "specialization": "General Medicine",
                "experience_years": 7,
                "consultation_fee": 600.0,
                "hospital_name": "Test Hospital",
                "bio": "Doctor",
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
        return user_id, doctor_id, headers

    def _lab(self, owner_user_id=None, verified=True):
        _, admin_headers = self._account("ADMIN")
        created = self.client.post(
            "/api/v1/providers",
            json={
                "code": f"L{uuid.uuid4().hex[:6].upper()}",
                "name": "Popular Diagnostic",
                "provider_type": "LAB",
                "district": "Dhaka",
                "owner_user_id": owner_user_id,
            },
            headers=admin_headers,
        )
        self.assertEqual(200, created.status_code, created.text)
        provider = created.json()
        if verified:
            self.client.patch(
                f"/api/v1/providers/{provider['id']}/verify", headers=admin_headers
            )
        return provider, admin_headers


class ProviderDirectoryTests(ProviderTestCase):
    def test_admin_can_register_and_verify_a_lab(self):
        provider, _ = self._lab()
        listing = self.client.get("/api/v1/providers?provider_type=LAB").json()
        self.assertIn(provider["id"], [p["id"] for p in listing["items"]])

    def test_patient_cannot_register_a_provider(self):
        _, _, headers = self._patient()
        response = self.client.post(
            "/api/v1/providers",
            json={
                "code": "DENY1",
                "name": "Nope",
                "provider_type": "LAB",
                "district": "Dhaka",
            },
            headers=headers,
        )
        self.assertEqual(403, response.status_code)

    def test_unverified_lab_cannot_receive_orders(self):
        owner_id, owner_headers = self._account("DOCTOR")
        provider, admin_headers = self._lab(owner_user_id=owner_id, verified=False)
        test = self.client.post(
            f"/api/v1/providers/{provider['id']}/tests",
            json={"code": "CBC", "name": "Complete Blood Count", "price_bdt": 400},
            headers=admin_headers,
        ).json()

        _, _, patient_headers = self._patient()
        response = self.client.post(
            "/api/v1/lab-orders",
            json={"provider_id": provider["id"], "lab_test_id": test["id"]},
            headers=patient_headers,
        )
        self.assertEqual(400, response.status_code)


class LabOrderTests(ProviderTestCase):
    def _ordered(self):
        owner_id, owner_headers = self._account("DOCTOR")
        provider, admin_headers = self._lab(owner_user_id=owner_id)
        test = self.client.post(
            f"/api/v1/providers/{provider['id']}/tests",
            json={
                "code": "CBC",
                "name": "Complete Blood Count",
                "price_bdt": 400,
                "sample_type": "blood",
            },
            headers=admin_headers,
        ).json()

        patient_user_id, patient_id, patient_headers = self._patient()
        order = self.client.post(
            "/api/v1/lab-orders",
            json={"provider_id": provider["id"], "lab_test_id": test["id"]},
            headers=patient_headers,
        )
        self.assertEqual(200, order.status_code, order.text)
        return {
            "order": order.json(),
            "provider": provider,
            "owner_headers": owner_headers,
            "patient_headers": patient_headers,
            "patient_user_id": patient_user_id,
            "patient_id": patient_id,
        }

    def test_order_lifecycle_to_result(self):
        context = self._ordered()
        order_id = context["order"]["id"]

        for status in ("ACCEPTED", "SAMPLE_COLLECTED", "PROCESSING"):
            response = self.client.patch(
                f"/api/v1/lab-orders/{order_id}/status",
                json={"status": status},
                headers=context["owner_headers"],
            )
            self.assertEqual(200, response.status_code, response.text)

        result = self.client.post(
            f"/api/v1/lab-orders/{order_id}/result",
            json={
                "result_summary": "Haemoglobin 9.1 g/dL - low",
                "result_values": {"haemoglobin": 9.1},
                "is_abnormal": True,
            },
            headers=context["owner_headers"],
        )
        self.assertEqual(200, result.status_code, result.text)
        self.assertEqual("REPORTED", result.json()["status"])

    def test_invalid_status_transition_is_rejected(self):
        context = self._ordered()
        response = self.client.patch(
            f"/api/v1/lab-orders/{context['order']['id']}/status",
            json={"status": "PROCESSING"},
            headers=context["owner_headers"],
        )
        self.assertEqual(409, response.status_code)

    def test_result_is_hidden_from_doctor_without_consent(self):
        context = self._ordered()
        order_id = context["order"]["id"]

        self.client.patch(
            f"/api/v1/lab-orders/{order_id}/consent",
            json={"share_with_doctor": False},
            headers=context["patient_headers"],
        )

        _, _, doctor_headers = self._doctor()
        response = self.client.get(
            f"/api/v1/lab-orders/{order_id}", headers=doctor_headers
        )
        self.assertEqual(403, response.status_code)

    def test_patient_always_sees_their_own_order(self):
        context = self._ordered()
        response = self.client.get(
            f"/api/v1/lab-orders/{context['order']['id']}",
            headers=context["patient_headers"],
        )
        self.assertEqual(200, response.status_code)

    def test_unrelated_patient_cannot_read_order(self):
        context = self._ordered()
        _, _, intruder = self._patient()
        response = self.client.get(
            f"/api/v1/lab-orders/{context['order']['id']}", headers=intruder
        )
        self.assertEqual(403, response.status_code)


class PharmacyStockTests(ProviderTestCase):
    def test_stock_search_matches_on_generic_not_brand(self):
        owner_id, owner_headers = self._account("DOCTOR")
        _, admin_headers = self._account("ADMIN")
        created = self.client.post(
            "/api/v1/providers",
            json={
                "code": f"P{uuid.uuid4().hex[:6].upper()}",
                "name": "Lazz Pharma",
                "provider_type": "PHARMACY",
                "district": "Dhaka",
                "owner_user_id": owner_id,
            },
            headers=admin_headers,
        ).json()

        self.client.post(
            f"/api/v1/providers/{created['id']}/stock",
            json={
                "brand_name": "Napa 500",
                "strength": "500mg",
                "unit_price_bdt": 1.2,
                "quantity_available": 500,
            },
            headers=owner_headers,
        )

        # Searching a different paracetamol brand must still find the stock.
        results = self.client.get("/api/v1/pharmacies/search?medicine=Ace 500").json()
        self.assertEqual("paracetamol", results["resolved_generic"])
        self.assertTrue(
            any(r["provider_id"] == created["id"] for r in results["results"])
        )


class PaymentTests(ProviderTestCase):
    def _appointment(self):
        patient_user_id, _, patient_headers = self._patient()
        _, doctor_id, doctor_headers = self._doctor()
        self.client.post(
            f"/api/v1/doctor-availability/{doctor_id}",
            json={
                "available_date": "2026-11-05",
                "start_time": "10:00",
                "end_time": "11:00",
            },
            headers=doctor_headers,
        )
        self.client.post(
            f"/api/v1/appointments/{patient_user_id}",
            json={
                "doctor_id": doctor_id,
                "appointment_date": "2026-11-05",
                "appointment_time": "10:00",
                "reason": "Consultation payment test",
            },
            headers=patient_headers,
        )
        appointments = self.client.get(
            f"/api/v1/appointments/patient/{patient_user_id}", headers=patient_headers
        ).json()
        return appointments[0]["id"], patient_headers

    def test_checkout_uses_the_doctor_fee_not_the_client(self):
        appointment_id, headers = self._appointment()
        response = self.client.post(
            "/api/v1/payments/checkout",
            json={
                "purpose": "CONSULTATION",
                "method": "bkash",
                "idempotency_key": uuid.uuid4().hex,
                "appointment_id": appointment_id,
            },
            headers=headers,
        )
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(600.0, response.json()["amount_bdt"])

    def test_checkout_is_idempotent(self):
        appointment_id, headers = self._appointment()
        key = uuid.uuid4().hex
        body = {
            "purpose": "CONSULTATION",
            "method": "bkash",
            "idempotency_key": key,
            "appointment_id": appointment_id,
        }
        first = self.client.post("/api/v1/payments/checkout", json=body, headers=headers)
        second = self.client.post("/api/v1/payments/checkout", json=body, headers=headers)
        self.assertEqual(first.json()["reference"], second.json()["reference"])

    def test_callback_requires_a_valid_signature(self):
        appointment_id, headers = self._appointment()
        payment = self.client.post(
            "/api/v1/payments/checkout",
            json={
                "purpose": "CONSULTATION",
                "method": "bkash",
                "idempotency_key": uuid.uuid4().hex,
                "appointment_id": appointment_id,
            },
            headers=headers,
        ).json()

        response = self.client.post(
            "/api/v1/payments/callback",
            json={
                "reference": payment["reference"],
                "status": "COMPLETED",
                "gateway_reference": "X",
                "signature": "0" * 64,
            },
        )
        self.assertEqual(401, response.status_code)

    def _complete(self, headers, appointment_id):
        payment = self.client.post(
            "/api/v1/payments/checkout",
            json={
                "purpose": "CONSULTATION",
                "method": "bkash",
                "idempotency_key": uuid.uuid4().hex,
                "appointment_id": appointment_id,
            },
            headers=headers,
        ).json()

        body = {
            "reference": payment["reference"],
            "status": "COMPLETED",
            "gateway_reference": payment["gateway_reference"],
        }
        signature = get_gateway("bkash").signature_for(body)
        callback = self.client.post(
            "/api/v1/payments/callback", json={**body, "signature": signature}
        )
        self.assertEqual(200, callback.status_code, callback.text)
        return payment, callback.json()

    def test_signed_callback_completes_the_payment(self):
        appointment_id, headers = self._appointment()
        _, completed = self._complete(headers, appointment_id)
        self.assertEqual("COMPLETED", completed["status"])

    def test_replayed_callback_does_not_change_a_terminal_payment(self):
        appointment_id, headers = self._appointment()
        payment, completed = self._complete(headers, appointment_id)

        body = {
            "reference": payment["reference"],
            "status": "FAILED",
            "gateway_reference": payment["gateway_reference"],
        }
        signature = get_gateway("bkash").signature_for(body)
        replay = self.client.post(
            "/api/v1/payments/callback", json={**body, "signature": signature}
        ).json()
        self.assertEqual("COMPLETED", replay["status"])

    def test_commission_is_recorded(self):
        appointment_id, headers = self._appointment()
        _, completed = self._complete(headers, appointment_id)
        self.assertGreater(completed["platform_fee_bdt"], 0)
        self.assertAlmostEqual(
            completed["amount_bdt"],
            completed["platform_fee_bdt"] + completed["payout_bdt"],
            places=2,
        )

    def test_refund_cannot_exceed_the_charge(self):
        appointment_id, headers = self._appointment()
        payment, _ = self._complete(headers, appointment_id)
        _, admin_headers = self._account("ADMIN")

        response = self.client.post(
            f"/api/v1/payments/{payment['id']}/refund",
            json={"amount_bdt": 99999.0},
            headers=admin_headers,
        )
        self.assertEqual(400, response.status_code)

    def test_full_refund_marks_the_payment_refunded(self):
        appointment_id, headers = self._appointment()
        payment, _ = self._complete(headers, appointment_id)
        _, admin_headers = self._account("ADMIN")

        response = self.client.post(
            f"/api/v1/payments/{payment['id']}/refund",
            json={},
            headers=admin_headers,
        )
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual("REFUNDED", response.json()["status"])

    def test_other_users_cannot_read_a_payment(self):
        appointment_id, headers = self._appointment()
        payment, _ = self._complete(headers, appointment_id)
        _, _, intruder = self._patient()
        response = self.client.get(
            f"/api/v1/payments/{payment['id']}", headers=intruder
        )
        self.assertEqual(403, response.status_code)

    def test_reconciliation_is_admin_only(self):
        _, _, patient_headers = self._patient()
        self.assertEqual(
            403,
            self.client.get(
                "/api/v1/payments/reconciliation", headers=patient_headers
            ).status_code,
        )

    def test_reconciliation_balances(self):
        _, admin_headers = self._account("ADMIN")
        report = self.client.get(
            "/api/v1/payments/reconciliation", headers=admin_headers
        ).json()
        self.assertAlmostEqual(
            report["gross_collected_bdt"] - report["refunded_bdt"],
            report["net_settlement_bdt"],
            places=2,
        )


class FhirTests(ProviderTestCase):
    def test_capability_statement_declares_r4(self):
        response = self.client.get("/api/v1/fhir/metadata")
        self.assertEqual(200, response.status_code)
        self.assertEqual("4.0.1", response.json()["fhirVersion"])

    def test_patient_resource_shape(self):
        user_id, patient_id, headers = self._patient()
        response = self.client.get(
            f"/api/v1/fhir/Patient/{patient_id}", headers=headers
        )
        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual("Patient", body["resourceType"])
        self.assertEqual("female", body["gender"])
        self.assertTrue(body["identifier"])

    def test_practitioner_carries_the_bmdc_identifier(self):
        _, doctor_id, _ = self._doctor()
        body = self.client.get(f"/api/v1/fhir/Practitioner/{doctor_id}").json()
        self.assertEqual("Practitioner", body["resourceType"])
        self.assertIn("bmdc", body["identifier"][0]["system"])

    def test_triage_maps_to_an_observation(self):
        _, patient_id, headers = self._patient()
        self.client.post(
            "/api/v1/triage/sessions",
            json={"symptoms": "বুকে ব্যথা, শ্বাস নিতে কষ্ট", "age_years": 50},
            headers=headers,
        )
        bundle = self.client.get(
            f"/api/v1/fhir/Patient/{patient_id}/$everything", headers=headers
        ).json()
        types = [e["resource"]["resourceType"] for e in bundle["entry"]]
        self.assertIn("Observation", types)

    def test_everything_bundle_is_a_document(self):
        _, patient_id, headers = self._patient()
        bundle = self.client.get(
            f"/api/v1/fhir/Patient/{patient_id}/$everything", headers=headers
        ).json()
        self.assertEqual("Bundle", bundle["resourceType"])
        self.assertEqual("document", bundle["type"])

    def test_patient_record_is_not_readable_by_another_patient(self):
        _, patient_id, _ = self._patient()
        _, _, intruder = self._patient()
        response = self.client.get(
            f"/api/v1/fhir/Patient/{patient_id}", headers=intruder
        )
        self.assertEqual(403, response.status_code)

    def test_fhir_requires_authentication(self):
        _, patient_id, _ = self._patient()
        response = self.client.get(f"/api/v1/fhir/Patient/{patient_id}")
        self.assertIn(response.status_code, (401, 403))


if __name__ == "__main__":
    unittest.main()
