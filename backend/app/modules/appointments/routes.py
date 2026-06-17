from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.schemas.appointment import (
    AppointmentCreate
)

from app.modules.appointments.service import (
    create_appointment_service
)

router = APIRouter()


@router.post(
    "/appointments/{patient_user_id}"
)
def create_appointment(
    patient_user_id: str,
    payload: AppointmentCreate,
    db: Session = Depends(get_db)
):
    return create_appointment_service(
        patient_user_id=patient_user_id,
        payload=payload,
        db=db
    )