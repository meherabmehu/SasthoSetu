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