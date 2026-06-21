from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.schemas.doctor_availability import (
    DoctorAvailabilityCreate
)

from app.modules.doctor_availability.service import (
    create_availability_service,
    get_doctor_availability_service
)

router = APIRouter()


@router.post(
    "/doctor-availability/{doctor_id}"
)
def create_availability(
    doctor_id: str,
    payload: DoctorAvailabilityCreate,
    db: Session = Depends(get_db)
):
    return create_availability_service(
        doctor_id=doctor_id,
        payload=payload,
        db=db
    )


@router.get(
    "/doctor-availability/{doctor_id}"
)
def get_doctor_availability(
    doctor_id: str,
    db: Session = Depends(get_db)
):
    return get_doctor_availability_service(
        doctor_id=doctor_id,
        db=db
    )