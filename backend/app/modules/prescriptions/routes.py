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
    get_patient_prescriptions_service,
    get_doctor_prescriptions_service
)
from app.core.security import (
    get_current_user,
    require_doctor,
    require_self_or_clinician,
)

router = APIRouter()


@router.post(
    "/prescriptions/{doctor_id}"
)
def create_prescription(
    doctor_id: str,
    payload: PrescriptionCreate,
    current_user=Depends(
        require_doctor
    ),
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
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    require_self_or_clinician(patient_user_id, current_user)
    return get_patient_prescriptions_service(
        patient_user_id=patient_user_id,
        db=db
    )


@router.get(
    "/prescriptions/doctor/{doctor_id}"
)
def get_doctor_prescriptions(
    doctor_id: str,
    current_user=Depends(require_doctor),
    db: Session = Depends(get_db)
):
    return get_doctor_prescriptions_service(
        doctor_id=doctor_id,
        db=db
    )