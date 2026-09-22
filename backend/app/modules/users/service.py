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

def update_own_profile_service(
    user_id: str,
    payload,
    db: Session
):
    """Change the name or phone number on the signed-in account.

    Phone numbers are unique across accounts, so a number that already
    belongs to someone else is rejected with 409 rather than an opaque
    integrity error from the database. The caller's own number is exempt:
    saving an unchanged profile must not collide with itself.
    """
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if payload.phone and payload.phone != user.phone:
        taken = (
            db.query(User)
            .filter(User.phone == payload.phone, User.id != user.id)
            .first()
        )
        if taken:
            raise HTTPException(
                status_code=409,
                detail="That phone number belongs to another account"
            )

    if payload.full_name:
        user.full_name = payload.full_name
    if payload.phone:
        user.phone = payload.phone

    db.commit()

    return {
        "message": "Profile updated",
        "full_name": user.full_name,
        "phone": user.phone,
    }
