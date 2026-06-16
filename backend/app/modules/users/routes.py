from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.schemas.user import UserCreate
from app.models.user import User
from app.core.dependencies import get_db

router = APIRouter()


@router.post("/users")
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db)
):
    user = User(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        password_hash=payload.password
    )

    db.add(user)
    db.commit()

    return {
        "message": "User created successfully"
    }