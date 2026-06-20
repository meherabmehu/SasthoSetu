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
from app.modules.appointments.service import (
    create_appointment_service,
    get_patient_appointments_service,
    get_doctor_appointments_service
)
from app.schemas.appointment_status import (
    AppointmentStatusUpdate
)
from app.modules.appointments.service import (
    create_appointment_service,
    get_patient_appointments_service,
    get_doctor_appointments_service,
    update_appointment_status_service
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

@router.get(
    "/appointments/patient/{patient_user_id}"
)
def get_patient_appointments(
    patient_user_id: str,
    db: Session = Depends(get_db)
):
    return get_patient_appointments_service(
        patient_user_id=patient_user_id,
        db=db
    )

@router.get(
    "/appointments/doctor/{doctor_id}"
)
def get_doctor_appointments(
    doctor_id: str,
    db: Session = Depends(get_db)
):
    return get_doctor_appointments_service(
        doctor_id=doctor_id,
        db=db
    )

@router.patch(
    "/appointments/{appointment_id}/status"
)
def update_appointment_status(
    appointment_id: str,
    payload: AppointmentStatusUpdate,
    db: Session = Depends(get_db)
):
    return update_appointment_status_service(
        appointment_id=appointment_id,
        status=payload.status,
        db=db
    )