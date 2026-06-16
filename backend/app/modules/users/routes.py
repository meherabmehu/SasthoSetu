from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.schemas.user import UserCreate
from app.models.user import User
from app.core.dependencies import get_db
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
router = APIRouter()


@router.post("/users")
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db)
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