# -*- coding: utf-8 -*-
"""Uploaded medical files survive without a local disk.

Uploads used to be written to an ``uploads/`` directory and the row kept only
the path. That silently loses every scan and report on any host that replaces
the instance - which is all of them, eventually, and a serverless host after
every request. The bytes now live in the row.

These tests hold that line, and cover the limits that come with accepting a
file into the database: a size ceiling, a type whitelist, and a filename that
cannot be used to escape the record it belongs to.
"""
import io
import os
import tempfile
import unittest
import uuid
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/files.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.file_record import FileRecord  # noqa: E402
from app.models.user import User  # noqa: E402
from app.modules.files.service import MAX_UPLOAD_BYTES  # noqa: E402

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
    b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class FileUploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app, raise_server_exceptions=False)

    def _patient(self):
        email = f"patient-{uuid.uuid4().hex[:8]}@example.com"
        password = "Passw0rd@123"
        self.client.post(
            "/api/v1/users",
            json={
                "full_name": "File Owner",
                "email": email,
                "phone": f"017{uuid.uuid4().int % 100000000:08d}",
                "password": password,
            },
        )
        session = SessionLocal()
        try:
            user_id = session.query(User).filter(User.email == email).first().id
        finally:
            session.close()

        login = self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

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
        self.assertIn(created.status_code, (200, 201))
        return user_id, headers

    def _upload(self, user_id, headers, name="scan.png",
                payload=PNG, content_type="image/png"):
        return self.client.post(
            f"/api/v1/files/upload/{user_id}",
            files={"file": (name, io.BytesIO(payload), content_type)},
            headers=headers,
        )

    def test_the_bytes_are_stored_in_the_row_not_on_disk(self):
        user_id, headers = self._patient()
        self.assertEqual(200, self._upload(user_id, headers).status_code)

        session = SessionLocal()
        try:
            record = (
                session.query(FileRecord)
                .filter(FileRecord.uploaded_by == user_id)
                .first()
            )
            self.assertIsNotNone(record)
            self.assertEqual(PNG, record.content)
            self.assertEqual(len(PNG), record.file_size)
            # A path would mean the bytes are somewhere that does not travel
            # with the database.
            self.assertIsNone(record.file_path)
        finally:
            session.close()

    def test_an_uploaded_file_can_be_downloaded_again(self):
        user_id, headers = self._patient()
        self._upload(user_id, headers)

        listing = self.client.get(f"/api/v1/files/{user_id}", headers=headers)
        self.assertEqual(200, listing.status_code)
        file_id = listing.json()[0]["id"]

        got = self.client.get(
            f"/api/v1/files/download/{file_id}", headers=headers
        )
        self.assertEqual(200, got.status_code)
        self.assertEqual(PNG, got.content)
        self.assertEqual("image/png", got.headers["content-type"])

    def test_a_file_larger_than_the_ceiling_is_refused(self):
        user_id, headers = self._patient()
        oversized = b"\x00" * (MAX_UPLOAD_BYTES + 1024)
        response = self._upload(user_id, headers, payload=oversized)
        self.assertEqual(413, response.status_code)

    def test_an_executable_disguised_as_a_record_is_refused(self):
        user_id, headers = self._patient()
        response = self._upload(
            user_id,
            headers,
            name="payload.sh",
            payload=b"#!/bin/sh\nrm -rf /\n",
            content_type="application/x-sh",
        )
        self.assertEqual(415, response.status_code)

    def test_an_empty_file_is_refused(self):
        user_id, headers = self._patient()
        response = self._upload(user_id, headers, payload=b"")
        self.assertEqual(400, response.status_code)

    def test_a_traversing_filename_is_reduced_to_its_base(self):
        """The name is echoed in a response header, so it cannot carry a path."""
        user_id, headers = self._patient()
        self._upload(user_id, headers, name="../../../etc/passwd.png")

        session = SessionLocal()
        try:
            record = (
                session.query(FileRecord)
                .filter(FileRecord.uploaded_by == user_id)
                .first()
            )
            self.assertEqual("passwd.png", record.file_name)
        finally:
            session.close()

    def test_another_patient_cannot_download_the_file(self):
        owner_id, owner = self._patient()
        self._upload(owner_id, owner)
        file_id = self.client.get(
            f"/api/v1/files/{owner_id}", headers=owner
        ).json()[0]["id"]

        _, attacker = self._patient()
        response = self.client.get(
            f"/api/v1/files/download/{file_id}", headers=attacker
        )
        self.assertEqual(403, response.status_code)


if __name__ == "__main__":
    unittest.main()
