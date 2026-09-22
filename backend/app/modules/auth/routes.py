from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.schemas.auth import (
    ChangePasswordRequest,
    CurrentUserResponse,
    LoginRequest,
)
from app.core.dependencies import get_db
from app.core.security import get_current_user

from app.modules.auth.service import (
    change_password_service,
    login_service
)

router = APIRouter()


@router.post("/login")
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db)
):
    return login_service(
        email=payload.email,
        password=payload.password,
        db=db
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
)
def get_my_identity(
    current_user=Depends(get_current_user),
):
    return current_user


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return change_password_service(
        user_id=current_user["user_id"],
        current_password=payload.current_password,
        new_password=payload.new_password,
        db=db
    )
