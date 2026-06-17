from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.schemas.user import UserCreate
from app.core.dependencies import get_db

from app.modules.users.service import (
    create_user_service
)

router = APIRouter()


@router.post("/users")
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db)
):
    return create_user_service(
        payload=payload,
        db=db
    )