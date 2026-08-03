from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import get_current_user, require_self_or_clinician

from app.modules.patient_history.service import (
    get_patient_history_service
)

router = APIRouter()


@router.get(
    "/patients/{patient_user_id}/history"
)
def get_patient_history(
    patient_user_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    require_self_or_clinician(patient_user_id, current_user)
    return get_patient_history_service(
        patient_user_id=patient_user_id,
        db=db
    )