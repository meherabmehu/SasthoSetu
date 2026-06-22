from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.modules.patient_history.service import (
    get_patient_history_service
)

router = APIRouter()


@router.get(
    "/patients/{patient_user_id}/history"
)
def get_patient_history(
    patient_user_id: str,
    db: Session = Depends(get_db)
):
    return get_patient_history_service(
        patient_user_id=patient_user_id,
        db=db
    )