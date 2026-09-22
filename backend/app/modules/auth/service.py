from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.models.user import User

from app.core.security import (
    verify_password,
    hash_password,
    create_access_token
)


def login_service(
    email: str,
    password: str,
    db: Session
):

    user = (
        db.query(User)
        .filter(
            User.email == email
        )
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is disabled",
        )

    if not verify_password(
        password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    token = create_access_token(
        {
            "sub": user.id,
            "user_id": user.id,
            "role": user.role
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


def change_password_service(
    user_id: str,
    current_password: str,
    new_password: str,
    db: Session
):
    """Set a new password for the signed-in account.

    The current password is required: without it, a browser left unlocked, a
    stolen token or a shared device is enough to lock the owner out and hand
    the attacker an account that still looks like theirs.

    The response is deliberately free of detail about the account beyond
    what the caller already knows by being signed in.
    """
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if not verify_password(
        current_password,
        user.password_hash
    ):
        # Deliberately 400 rather than 401: the client treats any 401 on an
        # authenticated call as an expired session and signs the user out,
        # so reusing it here would log someone out for a typo.
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect"
        )

    if current_password == new_password:
        raise HTTPException(
            status_code=400,
            detail="The new password must be different from the current one"
        )

    user.password_hash = hash_password(new_password)
    db.commit()

    return {
        "message": "Password updated. Use the new password next time you sign in."
    }
