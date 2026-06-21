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