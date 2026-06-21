from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.schemas.medical_record import (
    MedicalRecordCreate
)

from app.modules.medical_records.service import (
    create_medical_record_service
)
from app.modules.medical_records.service import (
    create_medical_record_service,
    get_patient_medical_records_service,
    get_doctor_medical_records_service
)

router = APIRouter()


@router.post(
    "/medical-records/{doctor_id}"
)
def create_medical_record(
    doctor_id: str,
    payload: MedicalRecordCreate,
    db: Session = Depends(get_db)
):
    return create_medical_record_service(
        doctor_id=doctor_id,
        payload=payload,
        db=db
    )

@router.get(
    "/medical-records/patient/{patient_user_id}"
)
def get_patient_medical_records(
    patient_user_id: str,
    db: Session = Depends(get_db)
):
    return get_patient_medical_records_service(
        patient_user_id=patient_user_id,
        db=db
    )


@router.get(
    "/medical-records/doctor/{doctor_id}"
)
def get_doctor_medical_records(
    doctor_id: str,
    db: Session = Depends(get_db)
):
    return get_doctor_medical_records_service(
        doctor_id=doctor_id,
        db=db
    )