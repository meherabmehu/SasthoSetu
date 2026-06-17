from fastapi import HTTPException

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.core.security import hash_password


def create_user_service(
    payload,
    db: Session
):
    try:

        user = User(
            full_name=payload.full_name,
            email=payload.email,
            phone=payload.phone,
            password_hash=hash_password(
                payload.password
            ),
            role="PATIENT"
        )

        db.add(user)
        db.commit()

        return {
            "message": "User created successfully"
        }

    except IntegrityError:

        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Email or phone already exists"
        )