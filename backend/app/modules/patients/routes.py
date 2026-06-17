from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.models.user import User
from app.models.patient import Patient

from app.schemas.patient import PatientCreate
from app.modules.patients.service import (
    create_patient_profile_service,
    get_patient_profile_service
)

router = APIRouter()


@router.post("/patients/{user_id}")
def create_patient_profile(
    user_id: str,
    payload: PatientCreate,
    db: Session = Depends(get_db)
):
    return create_patient_profile_service(
        user_id=user_id,
        payload=payload,
        db=db
    )

@router.get("/patients/{user_id}")
def get_patient_profile(
    user_id: str,
    db: Session = Depends(get_db)
):
    return get_patient_profile_service(
        user_id=user_id,
        db=db
    )