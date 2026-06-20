from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.schemas.prescription import (
    PrescriptionCreate
)

from app.modules.prescriptions.service import (
    create_prescription_service
)
from app.modules.prescriptions.service import (
    create_prescription_service,
    get_patient_prescriptions_service,
    get_doctor_prescriptions_service
)

router = APIRouter()


@router.post(
    "/prescriptions/{doctor_id}"
)
def create_prescription(
    doctor_id: str,
    payload: PrescriptionCreate,
    db: Session = Depends(get_db)
):
    return create_prescription_service(
        doctor_id=doctor_id,
        payload=payload,
        db=db
    )
@router.get(
    "/prescriptions/patient/{patient_user_id}"
)
def get_patient_prescriptions(
    patient_user_id: str,
    db: Session = Depends(get_db)
):
    return get_patient_prescriptions_service(
        patient_user_id=patient_user_id,
        db=db
    )


@router.get(
    "/prescriptions/doctor/{doctor_id}"
)
def get_doctor_prescriptions(
    doctor_id: str,
    db: Session = Depends(get_db)
):
    return get_doctor_prescriptions_service(
        doctor_id=doctor_id,
        db=db
    )