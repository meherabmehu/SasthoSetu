import unittest

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import (
    create_access_token,
    get_current_user,
    require_self_or_admin,
)
from app.models.base import Base
from app.models.user import User


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        session_factory = sessionmaker(bind=self.engine)
        self.db = session_factory()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _add_user(
        self,
        user_id: str,
        role: str = "PATIENT",
        is_active: bool = True,
    ):
        self.db.add(
            User(
                id=user_id,
                full_name="Test User",
                email=f"{user_id}@example.com",
                phone=f"01{len(user_id):09d}"[-11:],
                password_hash="not-used",
                role=role,
                is_active=is_active,
            )
        )
        self.db.commit()

    def _credentials(self, user_id: str):
        token = create_access_token(
            {"sub": user_id},
            expires_minutes=5,
        )
        return HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token,
        )

    def test_active_user_is_loaded_from_database(self):
        self._add_user("patient-1")

        current_user = get_current_user(
            credentials=self._credentials("patient-1"),
            db=self.db,
        )

        self.assertEqual(
            current_user,
            {"user_id": "patient-1", "role": "PATIENT"},
        )

    def test_disabled_user_cannot_use_existing_token(self):
        self._add_user("patient-2", is_active=False)

        with self.assertRaises(HTTPException) as context:
            get_current_user(
                credentials=self._credentials("patient-2"),
                db=self.db,
            )

        self.assertEqual(context.exception.status_code, 403)

    def test_deleted_user_token_is_rejected(self):
        with self.assertRaises(HTTPException) as context:
            get_current_user(
                credentials=self._credentials("missing-user"),
                db=self.db,
            )

        self.assertEqual(context.exception.status_code, 401)

    def test_user_can_access_own_resource(self):
        require_self_or_admin(
            "patient-1",
            {"user_id": "patient-1", "role": "PATIENT"},
        )

    def test_admin_can_access_another_users_resource(self):
        require_self_or_admin(
            "patient-1",
            {"user_id": "admin-1", "role": "ADMIN"},
        )

    def test_user_cannot_access_another_users_resource(self):
        with self.assertRaises(HTTPException) as context:
            require_self_or_admin(
                "patient-2",
                {"user_id": "patient-1", "role": "PATIENT"},
            )

        self.assertEqual(context.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
