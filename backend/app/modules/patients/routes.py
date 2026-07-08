from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import get_current_user, require_self_or_admin

from app.schemas.patient import PatientCreate
from app.modules.patients.service import (
    create_patient_profile_service,
    get_patient_profile_service
)

router = APIRouter()


@router.post("/patients/{user_id}")
def create_patient_profile(
    user_id: str,
    payload: PatientCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    require_self_or_admin(user_id, current_user)
    return create_patient_profile_service(
        user_id=user_id,
        payload=payload,
        db=db
    )

@router.get("/patients/{user_id}")
def get_patient_profile(
    user_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    require_self_or_admin(user_id, current_user)
    return get_patient_profile_service(
        user_id=user_id,
        db=db
    )
