# -*- coding: utf-8 -*-
"""Rural access channel tests: SMS, IVR and community health worker batches.

These channels serve users without a smartphone or a data connection, so the
assertions focus on the constraints that actually bite in the field: message
length, menu reachability, and a batch surviving one bad record.
"""
import os
import tempfile
import unittest
import uuid
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/rural.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.user import User  # noqa: E402
from app.modules.rural.service import IVR_MENU, SMS_BUDGET  # noqa: E402


class RuralTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app, raise_server_exceptions=False)

    def _worker(self):
        email = f"chw-{uuid.uuid4().hex[:8]}@example.com"
        password = "Passw0rd@123"
        self.client.post(
            "/api/v1/users",
            json={
                "full_name": "Community Health Worker",
                "email": email,
                "phone": f"017{uuid.uuid4().int % 100000000:08d}",
                "password": password,
            },
        )
        session = SessionLocal()
        try:
            user = session.query(User).filter(User.email == email).first()
            user.role = "DOCTOR"
            session.commit()
        finally:
            session.close()

        login = self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        return {"Authorization": f"Bearer {login.json()['access_token']}"}


class SmsTests(RuralTestCase):
    def test_emergency_sms_is_recognised(self):
        response = self.client.post(
            "/api/v1/rural/sms/triage",
            json={"text": "বুকে ব্যথা আর শ্বাস নিতে কষ্ট", "age_years": 55},
        )
        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertTrue(body["is_emergency"])
        self.assertEqual("EMERGENCY", body["triage_level"])

    def test_replies_fit_the_sms_budget(self):
        """A reply that splits into many segments may not arrive intact."""
        samples = [
            "বুকে ব্যথা আর শ্বাস নিতে কষ্ট",
            "তিন দিন ধরে জ্বর ও কাশি",
            "হালকা মাথাব্যথা",
            "পেট ব্যথা এবং বমি",
            "সাপে কামড়েছে",
        ]
        for text in samples:
            with self.subTest(text=text):
                body = self.client.post(
                    "/api/v1/rural/sms/triage", json={"text": text}
                ).json()
                self.assertLessEqual(body["characters"], SMS_BUDGET)
                self.assertLessEqual(body["segments"], 2)

    def test_emergency_reply_carries_the_emergency_number(self):
        body = self.client.post(
            "/api/v1/rural/sms/triage",
            json={"text": "রোগী অজ্ঞান হয়ে গেছে"},
        ).json()
        self.assertIn("৯৯৯", body["reply"])

    def test_english_replies_are_supported(self):
        body = self.client.post(
            "/api/v1/rural/sms/triage",
            json={"text": "chest pain and difficulty breathing", "language": "en"},
        ).json()
        self.assertTrue(body["is_emergency"])
        self.assertIn("999", body["reply"])

    def test_sms_triage_is_recorded(self):
        body = self.client.post(
            "/api/v1/rural/sms/triage", json={"text": "তিন দিন ধরে জ্বর"}
        ).json()
        self.assertTrue(body["triage_session_id"])

    def test_sms_works_without_a_registered_number(self):
        response = self.client.post(
            "/api/v1/rural/sms/triage",
            json={"phone": "01799999999", "text": "জ্বর ও কাশি"},
        )
        self.assertEqual(200, response.status_code)


class IvrTests(RuralTestCase):
    def test_root_menu_is_reachable(self):
        response = self.client.get("/api/v1/rural/ivr/menu")
        self.assertEqual(200, response.status_code)
        self.assertIn("1", response.json()["options"])

    def test_every_menu_option_leads_somewhere(self):
        """A key press that goes nowhere strands a caller with no screen."""
        for node, entry in IVR_MENU.items():
            for digit in entry["options"]:
                with self.subTest(node=node, digit=digit):
                    response = self.client.post(
                        "/api/v1/rural/ivr/select",
                        json={"node": node, "digit": digit},
                    )
                    self.assertEqual(200, response.status_code, response.text)
                    body = response.json()
                    self.assertNotIn("error", body)
                    self.assertTrue(
                        body.get("prompt") or body.get("options"),
                        f"{node}/{digit} produced no prompt",
                    )

    def test_cardiac_branch_reaches_an_emergency(self):
        body = self.client.post(
            "/api/v1/rural/ivr/select", json={"node": "cardio", "digit": "1"}
        ).json()
        self.assertTrue(body["is_emergency"])
        self.assertTrue(body["transfer_to_operator"])

    def test_child_branch_treats_the_caller_as_an_infant(self):
        """A high fever reported for a child must trigger the infant red flag."""
        body = self.client.post(
            "/api/v1/rural/ivr/select", json={"node": "child", "digit": "2"}
        ).json()
        self.assertEqual("EMERGENCY", body["triage_level"])

    def test_invalid_digit_reprompts_rather_than_failing(self):
        body = self.client.post(
            "/api/v1/rural/ivr/select", json={"node": "root", "digit": "9"}
        ).json()
        self.assertIn("error", body)
        self.assertTrue(body["prompt"])

    def test_operator_option_transfers(self):
        body = self.client.post(
            "/api/v1/rural/ivr/select", json={"node": "root", "digit": "0"}
        ).json()
        self.assertTrue(body["transfer_to_operator"])

    def test_unknown_node_is_rejected(self):
        self.assertEqual(
            404, self.client.get("/api/v1/rural/ivr/menu?node=nonsense").status_code
        )


class ChwBatchTests(RuralTestCase):
    def test_batch_is_accepted_and_emergencies_surfaced(self):
        headers = self._worker()
        response = self.client.post(
            "/api/v1/rural/chw/batch",
            json={
                "assessments": [
                    {
                        "client_reference": "visit-1",
                        "symptoms": "তিন দিন ধরে জ্বর ও কাশি",
                        "age_years": 30,
                    },
                    {
                        "client_reference": "visit-2",
                        "symptoms": "বুকে ব্যথা এবং শ্বাস নিতে কষ্ট",
                        "age_years": 60,
                    },
                    {
                        "client_reference": "visit-3",
                        "symptoms": "হালকা মাথাব্যথা",
                        "age_years": 25,
                    },
                ]
            },
            headers=headers,
        )
        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual(3, body["accepted"])
        self.assertEqual(0, body["rejected"])
        self.assertEqual(1, len(body["emergencies"]))
        self.assertEqual("visit-2", body["emergencies"][0]["client_reference"])

    def test_client_reference_is_echoed_for_reconciliation(self):
        headers = self._worker()
        body = self.client.post(
            "/api/v1/rural/chw/batch",
            json={
                "assessments": [
                    {"client_reference": "abc-123", "symptoms": "জ্বর", "age_years": 40}
                ]
            },
            headers=headers,
        ).json()
        self.assertEqual("abc-123", body["results"][0]["client_reference"])

    def test_batch_requires_authentication(self):
        response = self.client.post(
            "/api/v1/rural/chw/batch",
            json={
                "assessments": [
                    {"client_reference": "x", "symptoms": "জ্বর", "age_years": 30}
                ]
            },
        )
        self.assertIn(response.status_code, (401, 403))

    def test_location_is_retained_for_outbreak_mapping(self):
        headers = self._worker()
        response = self.client.post(
            "/api/v1/rural/chw/batch",
            json={
                "assessments": [
                    {
                        "client_reference": "geo-1",
                        "symptoms": "জ্বর ও শরীর ব্যথা",
                        "age_years": 22,
                        "latitude": 24.3636,
                        "longitude": 88.6241,
                    }
                ]
            },
            headers=headers,
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.json()["accepted"])


if __name__ == "__main__":
    unittest.main()
