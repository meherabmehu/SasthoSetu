from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt, JWTError

from fastapi import HTTPException
from fastapi import Depends
from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_db
from app.models.user import User

security = HTTPBearer()

# bcrypt operates on at most 72 bytes and raises beyond that. Passwords are
# truncated to the same boundary on hash and verify so a long passphrase
# authenticates consistently instead of erroring at the library layer.
BCRYPT_MAX_BYTES = 72


def _password_bytes(password: str) -> bytes:
    return (password or "").encode("utf-8")[:BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        _password_bytes(password),
        bcrypt.gensalt(),
    ).decode("utf-8")


def verify_password(
    plain_password: str,
    hashed_password: str,
):
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            _password_bytes(plain_password),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(
    data: dict,
    expires_minutes: int | None = None,
):
    payload = data.copy()
    identity = payload.get("sub") or payload.get("user_id")
    if not identity:
        raise ValueError("Token data must include sub or user_id")
    payload["sub"] = str(identity)

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=(
            expires_minutes
            if expires_minutes is not None
            else settings.access_token_expire_minutes
        )
    )

    payload.update(
        {
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
    )

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.jwt_algorithm
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
    db: Session = Depends(get_db),
):

    token = credentials.credentials

    try:

        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token subject",
            )

        user = (
            db.query(User)
            .filter(User.id == user_id)
            .first()
        )
        if not user:
            raise HTTPException(
                status_code=401,
                detail="User no longer exists",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=403,
                detail="User account is disabled",
            )

        return {
            "user_id": user.id,
            "role": user.role,
        }

    except JWTError:

        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )


def require_self_or_admin(
    target_user_id: str,
    current_user: dict,
) -> None:
    if (
        current_user.get("user_id") != target_user_id
        and current_user.get("role") != "ADMIN"
    ):
        raise HTTPException(
            status_code=403,
            detail="You cannot access another user's resource",
        )


def require_admin(
    current_user=Depends(
        get_current_user
    )
):

    if current_user.get("role") != "ADMIN":

        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return current_user


def require_doctor(
    current_user=Depends(
        get_current_user
    )
):

    if current_user.get("role") != "DOCTOR":

        raise HTTPException(
            status_code=403,
            detail="Doctor access required"
        )

    return current_user