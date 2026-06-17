from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.schemas.auth import LoginRequest
from app.core.dependencies import get_db

from app.modules.auth.service import (
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