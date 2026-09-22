# -*- coding: utf-8 -*-
"""Editing your own profile.

A name and a phone number are typed once, at registration, and people make
mistakes or change numbers. Until this endpoint existed the only way to fix
either was to ask an administrator to edit the database.

The rules under test:

  - a signed-in account can change its own name and phone;
  - a phone number that belongs to another account is refused with 409, not
    an opaque database error;
  - saving your own unchanged number does not collide with the uniqueness
    constraint;
  - email and role cannot be changed here, because the request schema does
    not accept them at all;
  - the identity endpoint reports the profile so the form can be prefilled.
"""
import os
import tempfile
import unittest
import uuid
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/profile.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402

PASSWORD = "Passw0rd@123"


class ProfileUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app, raise_server_exceptions=False)

    def _account(self, phone=None):
        email = f"profile-{uuid.uuid4().hex[:8]}@example.com"
        phone = phone or f"017{uuid.uuid4().int % 100000000:08d}"
        self.client.post(
            "/api/v1/users",
            json={
                "full_name": "Original Name",
                "email": email,
                "phone": phone,
                "password": PASSWORD,
            },
        )
        login = self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        return email, phone, headers

    def test_requires_a_token(self):
        self.assertEqual(
            401,
            self.client.patch(
                "/api/v1/users/me", json={"full_name": "No Token"}
            ).status_code,
        )

    def test_name_and_phone_can_be_changed(self):
        email, _, headers = self._account()
        new_phone = f"018{uuid.uuid4().int % 100000000:08d}"
        response = self.client.patch(
            "/api/v1/users/me",
            json={"full_name": "Corrected Name", "phone": new_phone},
            headers=headers,
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("Corrected Name", response.json()["full_name"])
        self.assertEqual(new_phone, response.json()["phone"])

        me = self.client.get("/api/v1/auth/me", headers=headers).json()
        self.assertEqual("Corrected Name", me["full_name"])
        self.assertEqual(new_phone, me["phone"])

    def test_an_unchanged_phone_does_not_collide_with_itself(self):
        email, phone, headers = self._account()
        response = self.client.patch(
            "/api/v1/users/me",
            json={"full_name": "Same Number", "phone": phone},
            headers=headers,
        )
        self.assertEqual(200, response.status_code)

    def test_someone_elses_phone_is_refused(self):
        _, other_phone, _ = self._account()
        email, phone, headers = self._account()
        response = self.client.patch(
            "/api/v1/users/me",
            json={"phone": other_phone},
            headers=headers,
        )
        self.assertEqual(409, response.status_code)
        # The account is untouched.
        me = self.client.get("/api/v1/auth/me", headers=headers).json()
        self.assertEqual(phone, me["phone"])

    def test_a_malformed_phone_is_refused(self):
        _, _, headers = self._account()
        for bad in ("12345", "02123456789", "017123456789"):
            with self.subTest(phone=bad):
                self.assertEqual(
                    422,
                    self.client.patch(
                        "/api/v1/users/me", json={"phone": bad}, headers=headers
                    ).status_code,
                )

    def test_email_and_role_are_not_even_acceptable_input(self):
        email, _, headers = self._account()
        # A caller trying to promote themselves: the field is simply not in
        # the schema, so it is ignored rather than applied.
        response = self.client.patch(
            "/api/v1/users/me",
            json={"full_name": "Harmless", "role": "ADMIN", "email": "x@y.com"},
            headers=headers,
        )
        self.assertEqual(200, response.status_code)

        session = SessionLocal()
        try:
            from app.models.user import User
            row = session.query(User).filter(User.email == email).first()
            self.assertEqual("PATIENT", row.role)
            self.assertEqual(email, row.email)
        finally:
            session.close()

    def test_the_identity_carries_the_profile(self):
        email, phone, headers = self._account()
        me = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(200, me.status_code)
        body = me.json()
        self.assertEqual("Original Name", body["full_name"])
        self.assertEqual(phone, body["phone"])


if __name__ == "__main__":
    unittest.main()
