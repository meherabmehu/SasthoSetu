from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.schemas.doctor import DoctorCreate

from app.modules.doctors.service import (
    create_doctor_profile_service
)

router = APIRouter()


@router.post("/doctors/{user_id}")
def create_doctor_profile(
    user_id: str,
    payload: DoctorCreate,
    db: Session = Depends(get_db)
):
    return create_doctor_profile_service(
        user_id=user_id,
        payload=payload,
        db=db
    )