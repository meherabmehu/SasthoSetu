# -*- coding: utf-8 -*-
"""Changing your own password.

The demo accounts ship with publicly documented passwords, so a way to
change them is not a convenience - it is the only thing standing between
"change the demo passwords before going public" and an instruction to run
SQL against the production database.

The rules under test:

  - the current password is required, so a borrowed session cannot silently
    take the account over;
  - the new password is only accepted with proof of the old one;
  - after a change the old password stops working and the new one works;
  - the request does nothing without a token.
"""
import os
import tempfile
import unittest
import uuid
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/pw.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.user import User  # noqa: E402

PASSWORD = "Passw0rd@123"
REPLACEMENT = "NayaPassw0rd@456"


class ChangePasswordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app, raise_server_exceptions=False)

    def _account(self):
        email = f"pw-{uuid.uuid4().hex[:8]}@example.com"
        self.client.post(
            "/api/v1/users",
            json={
                "full_name": "Password Changer",
                "email": email,
                "phone": f"017{uuid.uuid4().int % 100000000:08d}",
                "password": PASSWORD,
            },
        )
        login = self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        return email, headers

    def test_requires_a_token(self):
        self.assertEqual(
            401,
            self.client.post(
                "/api/v1/auth/change-password",
                json={"current_password": PASSWORD, "new_password": REPLACEMENT},
            ).status_code,
        )

    def test_the_current_password_must_be_correct(self):
        email, headers = self._account()
        response = self.client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "not-the-password", "new_password": REPLACEMENT},
            headers=headers,
        )
        # 400, not 401: the client reads 401 on an authenticated call as an
        # expired session and signs the user out, so a typo in the current
        # password must not end the session.
        self.assertEqual(400, response.status_code)

        # And the account is untouched.
        still = self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
        self.assertEqual(200, still.status_code)
        # The session also survives the rejected attempt.
        me = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(200, me.status_code)

    def test_a_short_new_password_is_refused(self):
        _, headers = self._account()
        response = self.client.post(
            "/api/v1/auth/change-password",
            json={"current_password": PASSWORD, "new_password": "short"},
            headers=headers,
        )
        self.assertEqual(422, response.status_code)

    def test_the_same_password_again_is_refused(self):
        _, headers = self._account()
        response = self.client.post(
            "/api/v1/auth/change-password",
            json={"current_password": PASSWORD, "new_password": PASSWORD},
            headers=headers,
        )
        self.assertEqual(400, response.status_code)

    def test_a_change_swaps_old_for_new(self):
        email, headers = self._account()
        response = self.client.post(
            "/api/v1/auth/change-password",
            json={"current_password": PASSWORD, "new_password": REPLACEMENT},
            headers=headers,
        )
        self.assertEqual(200, response.status_code)

        old = self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
        self.assertEqual(401, old.status_code)

        new = self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": REPLACEMENT}
        )
        self.assertEqual(200, new.status_code)

    def test_the_hash_is_rehashed_not_stored_plainly(self):
        email, headers = self._account()
        self.client.post(
            "/api/v1/auth/change-password",
            json={"current_password": PASSWORD, "new_password": REPLACEMENT},
            headers=headers,
        )
        session = SessionLocal()
        try:
            row = session.query(User).filter(User.email == email).first()
            self.assertNotEqual(REPLACEMENT, row.password_hash)
            self.assertTrue(row.password_hash.startswith("$2"))
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
