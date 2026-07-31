# -*- coding: utf-8 -*-
"""Hospital capacity, authorisation and emergency-routing tests."""
import os
import tempfile
import unittest
import uuid
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/hospitals.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.user import User  # noqa: E402


def unique_email(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def unique_phone():
    return f"017{uuid.uuid4().int % 100000000:08d}"


class HospitalTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app, raise_server_exceptions=False)

    def _register(self, role="PATIENT"):
        """Register a user and, when a privileged role is needed, elevate it.

        Public registration always creates a PATIENT by design, so elevation is
        done directly against the database rather than through the API.
        """
        email = unique_email(role.lower())
        password = "Passw0rd@123"
        response = self.client.post(
            "/api/v1/users",
            json={
                "full_name": f"Test {role}",
                "email": email,
                "phone": unique_phone(),
                "password": password,
            },
        )
        self.assertIn(response.status_code, (200, 201), response.text)

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
        self.assertEqual(200, login.status_code, login.text)
        token = login.json()["access_token"]
        return user_id, {"Authorization": f"Bearer {token}"}

    def _admin(self):
        return self._register("ADMIN")

    def _make_hospital(self, headers, **overrides):
        payload = {
            "code": f"H{uuid.uuid4().hex[:6].upper()}",
            "name": "Test General Hospital",
            "district": "Dhaka",
            "area": "Mirpur",
            "latitude": 23.80,
            "longitude": 90.36,
            "has_emergency": True,
        }
        payload.update(overrides)
        response = self.client.post(
            "/api/v1/hospitals", json=payload, headers=headers
        )
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    def _make_ward(self, hospital_id, headers, ward_type="icu", total=10, occupied=0):
        response = self.client.post(
            f"/api/v1/hospitals/{hospital_id}/wards",
            json={
                "ward_type": ward_type,
                "name": f"{ward_type.upper()} Ward",
                "total_beds": total,
                "occupied_beds": occupied,
            },
            headers=headers,
        )
        self.assertEqual(200, response.status_code, response.text)
        return response.json()


class HospitalCrudTests(HospitalTestCase):
    def test_admin_can_create_and_read_hospital(self):
        _, headers = self._admin()
        hospital = self._make_hospital(headers)
        fetched = self.client.get(f"/api/v1/hospitals/{hospital['id']}")
        self.assertEqual(200, fetched.status_code)
        self.assertEqual(hospital["code"], fetched.json()["code"])

    def test_hospital_is_addressable_by_code(self):
        _, headers = self._admin()
        hospital = self._make_hospital(headers)
        fetched = self.client.get(f"/api/v1/hospitals/{hospital['code']}")
        self.assertEqual(200, fetched.status_code)

    def test_patient_cannot_create_hospital(self):
        _, headers = self._register("PATIENT")
        response = self.client.post(
            "/api/v1/hospitals",
            json={"code": "HDENY", "name": "Nope", "district": "Dhaka"},
            headers=headers,
        )
        self.assertEqual(403, response.status_code)

    def test_anonymous_cannot_create_hospital(self):
        response = self.client.post(
            "/api/v1/hospitals",
            json={"code": "HANON", "name": "Nope", "district": "Dhaka"},
        )
        self.assertIn(response.status_code, (401, 403))

    def test_duplicate_code_rejected(self):
        _, headers = self._admin()
        hospital = self._make_hospital(headers)
        response = self.client.post(
            "/api/v1/hospitals",
            json={
                "code": hospital["code"],
                "name": "Duplicate",
                "district": "Dhaka",
            },
            headers=headers,
        )
        self.assertEqual(409, response.status_code)

    def test_unknown_hospital_returns_404(self):
        self.assertEqual(
            404, self.client.get("/api/v1/hospitals/does-not-exist").status_code
        )

    def test_list_is_paginated(self):
        _, headers = self._admin()
        for _ in range(3):
            self._make_hospital(headers)
        response = self.client.get("/api/v1/hospitals?limit=2&offset=0")
        self.assertEqual(200, response.status_code)
        self.assertLessEqual(len(response.json()["items"]), 2)
        self.assertIn("total", response.json())


class BedCapacityTests(HospitalTestCase):
    def test_ward_creation_and_availability_maths(self):
        _, headers = self._admin()
        hospital = self._make_hospital(headers)
        ward = self._make_ward(hospital["id"], headers, total=20, occupied=15)
        self.assertEqual(5, ward["available_beds"])
        self.assertEqual(0.75, ward["occupancy_rate"])

    def test_occupied_cannot_exceed_total_on_create(self):
        _, headers = self._admin()
        hospital = self._make_hospital(headers)
        response = self.client.post(
            f"/api/v1/hospitals/{hospital['id']}/wards",
            json={
                "ward_type": "general",
                "name": "General",
                "total_beds": 5,
                "occupied_beds": 9,
            },
            headers=headers,
        )
        self.assertEqual(400, response.status_code)

    def test_occupied_cannot_exceed_total_on_update(self):
        _, headers = self._admin()
        hospital = self._make_hospital(headers)
        ward = self._make_ward(hospital["id"], headers, total=10)
        response = self.client.patch(
            f"/api/v1/wards/{ward['id']}/bed-status",
            json={"occupied_beds": 99},
            headers=headers,
        )
        self.assertEqual(400, response.status_code)

    def test_duplicate_ward_type_rejected(self):
        _, headers = self._admin()
        hospital = self._make_hospital(headers)
        self._make_ward(hospital["id"], headers, ward_type="icu")
        response = self.client.post(
            f"/api/v1/hospitals/{hospital['id']}/wards",
            json={
                "ward_type": "icu",
                "name": "Second ICU",
                "total_beds": 4,
                "occupied_beds": 0,
            },
            headers=headers,
        )
        self.assertEqual(409, response.status_code)

    def test_bed_update_is_recorded_in_history(self):
        _, headers = self._admin()
        hospital = self._make_hospital(headers)
        ward = self._make_ward(hospital["id"], headers, total=10, occupied=2)

        self.client.patch(
            f"/api/v1/wards/{ward['id']}/bed-status",
            json={"occupied_beds": 7},
            headers=headers,
        )
        history = self.client.get(f"/api/v1/wards/{ward['id']}/history")
        self.assertEqual(200, history.status_code)
        self.assertGreaterEqual(len(history.json()), 2)
        self.assertEqual(7, history.json()[0]["occupied_beds"])

    def test_unassigned_staff_cannot_update_capacity(self):
        _, admin_headers = self._admin()
        hospital = self._make_hospital(admin_headers)
        ward = self._make_ward(hospital["id"], admin_headers)

        _, outsider = self._register("DOCTOR")
        response = self.client.patch(
            f"/api/v1/wards/{ward['id']}/bed-status",
            json={"occupied_beds": 1},
            headers=outsider,
        )
        self.assertEqual(403, response.status_code)

    def test_assigned_staff_can_update_their_own_hospital(self):
        _, admin_headers = self._admin()
        hospital = self._make_hospital(admin_headers)
        ward = self._make_ward(hospital["id"], admin_headers, total=10)

        staff_id, staff_headers = self._register("DOCTOR")
        assign = self.client.post(
            f"/api/v1/hospitals/{hospital['id']}/staff",
            json={"user_id": staff_id, "staff_role": "WARD_MANAGER"},
            headers=admin_headers,
        )
        self.assertEqual(200, assign.status_code, assign.text)

        response = self.client.patch(
            f"/api/v1/wards/{ward['id']}/bed-status",
            json={"occupied_beds": 3},
            headers=staff_headers,
        )
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(3, response.json()["occupied_beds"])

    def test_staff_cannot_update_a_different_hospital(self):
        _, admin_headers = self._admin()
        mine = self._make_hospital(admin_headers)
        theirs = self._make_hospital(admin_headers)
        other_ward = self._make_ward(theirs["id"], admin_headers)

        staff_id, staff_headers = self._register("DOCTOR")
        self.client.post(
            f"/api/v1/hospitals/{mine['id']}/staff",
            json={"user_id": staff_id},
            headers=admin_headers,
        )

        response = self.client.patch(
            f"/api/v1/wards/{other_ward['id']}/bed-status",
            json={"occupied_beds": 1},
            headers=staff_headers,
        )
        self.assertEqual(403, response.status_code)


class EmergencyRoutingTests(HospitalTestCase):
    def test_full_hospitals_are_excluded_when_a_bed_is_required(self):
        _, headers = self._admin()
        full = self._make_hospital(headers, name="Full Hospital")
        self._make_ward(full["id"], headers, ward_type="icu", total=5, occupied=5)

        results = self.client.get(
            "/api/v1/hospitals/nearby?ward_type=icu&emergency=true"
        ).json()
        self.assertNotIn(full["id"], [r["id"] for r in results])

    def test_hospital_with_free_icu_is_returned(self):
        _, headers = self._admin()
        open_hospital = self._make_hospital(headers, name="Open Hospital")
        self._make_ward(
            open_hospital["id"], headers, ward_type="icu", total=5, occupied=1
        )

        results = self.client.get(
            "/api/v1/hospitals/nearby?ward_type=icu&emergency=true"
        ).json()
        matched = [r for r in results if r["id"] == open_hospital["id"]]
        self.assertTrue(matched)
        self.assertEqual("icu", matched[0]["matched_ward"])
        self.assertGreater(matched[0]["available_icu_beds"], 0)

    def test_results_are_sorted_by_distance_when_coordinates_given(self):
        _, headers = self._admin()
        near = self._make_hospital(
            headers, name="Near", latitude=23.7500, longitude=90.3900
        )
        far = self._make_hospital(
            headers, name="Far", latitude=24.9000, longitude=91.8700
        )
        for hospital in (near, far):
            self._make_ward(
                hospital["id"], headers, ward_type="general", total=10, occupied=1
            )

        results = self.client.get(
            "/api/v1/hospitals/nearby"
            "?latitude=23.7500&longitude=90.3900&ward_type=general"
        ).json()
        ids = [r["id"] for r in results]
        self.assertIn(near["id"], ids)
        if far["id"] in ids:
            self.assertLess(ids.index(near["id"]), ids.index(far["id"]))

    def test_distance_is_none_without_coordinates(self):
        _, headers = self._admin()
        hospital = self._make_hospital(headers)
        self._make_ward(hospital["id"], headers, ward_type="general", total=4)
        results = self.client.get("/api/v1/hospitals/nearby?ward_type=general").json()
        matched = [r for r in results if r["id"] == hospital["id"]]
        self.assertIsNone(matched[0]["distance_km"])


if __name__ == "__main__":
    unittest.main()
