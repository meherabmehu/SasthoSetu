from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.schemas.doctor import DoctorCreate

from app.modules.doctors.service import (
    create_doctor_profile_service,
    get_all_doctors_service,
    get_doctor_by_id_service,
    get_doctors_by_specialization_service
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

@router.get("/doctors")
def get_all_doctors(
    db: Session = Depends(get_db)
):
    return get_all_doctors_service(
        db=db
    )


@router.get("/doctors/id/{doctor_id}")
def get_doctor_by_id(
    doctor_id: str,
    db: Session = Depends(get_db)
):
    return get_doctor_by_id_service(
        doctor_id=doctor_id,
        db=db
    )


@router.get(
    "/doctors/specialization/{specialization}"
)
def get_doctors_by_specialization(
    specialization: str,
    db: Session = Depends(get_db)
):
    return get_doctors_by_specialization_service(
        specialization=specialization,
        db=db
    )