from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

from fastapi import HTTPException
from fastapi import Depends
from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)

from app.core.config import settings

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

security = HTTPBearer()


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
):
    return pwd_context.verify(
        plain_password,
        hashed_password
    )


def create_access_token(
    data: dict,
    expires_minutes: int | None = None,
):
    payload = data.copy()

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
    )
):

    token = credentials.credentials

    try:

        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        return payload

    except JWTError:

        raise HTTPException(
            status_code=401,
            detail="Invalid token"
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
