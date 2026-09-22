from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.schemas.user import UserCreate, UserUpdateRequest
from app.core.dependencies import get_db
from app.core.security import get_current_user

from app.modules.users.service import (
    create_user_service,
    update_own_profile_service
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


@router.patch("/users/me")
def update_own_profile(
    payload: UserUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return update_own_profile_service(
        user_id=current_user["user_id"],
        payload=payload,
        db=db
    )
