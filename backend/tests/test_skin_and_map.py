# -*- coding: utf-8 -*-
"""Image assessment and the map endpoint.

Two features that go beyond text: a photograph of a skin lesion, and hospital
coordinates so a client can draw a map. Both are gated behind a login like
every other clinical feature.
"""
import io
import os
import tempfile
import unittest
import uuid
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/skin.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.ai.skin_features import FEATURE_NAMES, extract_features  # noqa: E402
from app.core.database import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402


def _photo(colour=(180, 140, 120), size=(200, 200), blob=True):
    """A synthetic photograph, optionally with a dark lesion in the middle."""
    image = Image.new("RGB", size, colour)
    if blob:
        pixels = image.load()
        cx, cy = size[0] // 2, size[1] // 2
        radius = min(size) // 4
        for x in range(size[0]):
            for y in range(size[1]):
                if (x - cx) ** 2 + (y - cy) ** 2 < radius ** 2:
                    pixels[x, y] = (60, 40, 35)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


class SkinFeatureTests(unittest.TestCase):
    """The measurements must be stable and finite whatever arrives."""

    def test_feature_count_matches_the_declared_names(self):
        vector = extract_features(Image.open(io.BytesIO(_photo())))
        self.assertEqual(len(FEATURE_NAMES), len(vector))

    def test_features_are_finite(self):
        import numpy as np

        for kwargs in ({}, {"blob": False}, {"size": (40, 40)},
                       {"colour": (255, 255, 255)}, {"colour": (0, 0, 0)}):
            with self.subTest(**kwargs):
                vector = extract_features(Image.open(io.BytesIO(_photo(**kwargs))))
                self.assertTrue(np.isfinite(vector).all())

    def test_a_dark_lesion_reads_darker_than_bare_skin(self):
        with_blob = extract_features(Image.open(io.BytesIO(_photo())))
        without = extract_features(Image.open(io.BytesIO(_photo(blob=False))))

        index = FEATURE_NAMES.index("lesion_r_mean")
        self.assertLess(
            with_blob[index], without[index],
            "a lesion darker than the surrounding skin must measure darker",
        )

    def test_the_extractor_is_deterministic(self):
        payload = _photo()
        first = extract_features(Image.open(io.BytesIO(payload)))
        second = extract_features(Image.open(io.BytesIO(payload)))
        self.assertTrue((first == second).all())


class SkinEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app, raise_server_exceptions=False)

    def _headers(self):
        email = f"skin-{uuid.uuid4().hex[:8]}@example.com"
        password = "Passw0rd@123"
        self.client.post("/api/v1/users", json={
            "full_name": "Skin Tester", "email": email,
            "phone": f"017{uuid.uuid4().int % 100000000:08d}",
            "password": password,
        })
        login = self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def test_an_anonymous_caller_cannot_upload(self):
        """A photograph of your own body is health data."""
        response = self.client.post(
            "/api/v1/ai/skin-check",
            files={"image": ("l.jpg", _photo(), "image/jpeg")},
        )
        self.assertEqual(401, response.status_code)

    def test_a_file_that_is_not_an_image_is_rejected(self):
        response = self.client.post(
            "/api/v1/ai/skin-check",
            files={"image": ("x.jpg", b"this is not a jpeg", "image/jpeg")},
            headers=self._headers(),
        )
        self.assertIn(response.status_code, (400, 503))
        if response.status_code == 400:
            self.assertIn("image", response.json()["detail"].lower())

    def test_an_empty_upload_is_rejected(self):
        response = self.client.post(
            "/api/v1/ai/skin-check",
            files={"image": ("x.jpg", b"", "image/jpeg")},
            headers=self._headers(),
        )
        self.assertIn(response.status_code, (400, 503))

    def test_a_photograph_returns_a_referral_band(self):
        response = self.client.post(
            "/api/v1/ai/skin-check",
            files={"image": ("l.jpg", _photo(), "image/jpeg")},
            data={"age_years": "45"},
            headers=self._headers(),
        )

        if response.status_code == 503:
            self.skipTest("skin model not built in this environment")

        self.assertEqual(200, response.status_code, response.text)
        body = response.json()

        self.assertIn(body["band"],
                      {"see_doctor_soon", "get_it_checked", "watch_it"})
        # A patient must never be handed a bare cancer name with no context.
        self.assertTrue(body["disclaimer_bn"])
        self.assertTrue(body["advice_bn"])
        self.assertTrue(body["differential"])

    def test_the_status_endpoint_needs_a_token(self):
        self.assertEqual(
            401, self.client.get("/api/v1/ai/skin-check/status").status_code
        )


class HospitalCoordinateTests(unittest.TestCase):
    """The map cannot draw a pin without coordinates."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app, raise_server_exceptions=False)

    def _admin(self):
        from app.core.database import SessionLocal
        from app.models.user import User

        email = f"map-{uuid.uuid4().hex[:8]}@example.com"
        password = "Passw0rd@123"
        self.client.post("/api/v1/users", json={
            "full_name": "Map Admin", "email": email,
            "phone": f"017{uuid.uuid4().int % 100000000:08d}",
            "password": password,
        })
        session = SessionLocal()
        try:
            user = session.query(User).filter(User.email == email).first()
            user.role = "ADMIN"
            session.commit()
        finally:
            session.close()

        login = self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def test_nearby_returns_coordinates(self):
        headers = self._admin()

        created = self.client.post("/api/v1/hospitals", json={
            "code": f"MAP{uuid.uuid4().hex[:5].upper()}",
            "name": "Map Test Hospital",
            "district": "Dhaka",
            "latitude": 23.78,
            "longitude": 90.40,
            "has_emergency": True,
        }, headers=headers)
        self.assertIn(created.status_code, (200, 201), created.text)

        response = self.client.get(
            "/api/v1/hospitals/nearby"
            "?latitude=23.78&longitude=90.40&require_bed=false&limit=5",
            headers=headers,
        )
        self.assertEqual(200, response.status_code, response.text)

        rows = response.json()
        self.assertTrue(rows, "no hospitals returned")
        for row in rows:
            with self.subTest(name=row["name"]):
                self.assertIn("latitude", row)
                self.assertIn("longitude", row)


if __name__ == "__main__":
    unittest.main()
