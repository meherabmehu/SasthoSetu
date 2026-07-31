from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.schemas.doctor import DoctorCreate

from app.modules.doctors.service import (
    create_doctor_profile_service,
    get_my_doctor_profile_service,
    get_all_doctors_service,
    get_doctor_by_id_service,
    get_doctors_by_specialization_service,
    get_pending_doctors_service,
    verify_doctor_service
)
from app.core.security import (
    get_current_user,
    require_admin,
    require_self_or_admin,
)

router = APIRouter()


@router.get("/doctors/me")
def get_my_doctor_profile(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_my_doctor_profile_service(
        current_user=current_user,
        db=db
    )


@router.post("/doctors/{user_id}")
def create_doctor_profile(
    user_id: str,
    payload: DoctorCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    require_self_or_admin(user_id, current_user)
    return create_doctor_profile_service(
        user_id=user_id,
        payload=payload,
        db=db
    )


@router.get("/doctors")
def get_all_doctors(
    db: Session = Depends(get_db)
):
    return get_all_doctors_service(
        db=db
    )


@router.get("/doctors/id/{doctor_id}")
def get_doctor_by_id(
    doctor_id: str,
    db: Session = Depends(get_db)
):
    return get_doctor_by_id_service(
        doctor_id=doctor_id,
        db=db
    )


@router.get(
    "/doctors/specialization/{specialization}"
)
def get_doctors_by_specialization(
    specialization: str,
    db: Session = Depends(get_db)
):
    return get_doctors_by_specialization_service(
        specialization=specialization,
        db=db
    )


@router.get(
    "/doctors/pending",
    dependencies=[Depends(require_admin)],
)
def get_pending_doctors(
    db: Session = Depends(get_db)
):
    return get_pending_doctors_service(
        db=db
    )


@router.patch("/doctors/{doctor_id}/verify")
def verify_doctor(
    doctor_id: str,
    current_user=Depends(
        require_admin
    ),
    db: Session = Depends(get_db)
):
    return verify_doctor_service(
        doctor_id=doctor_id,
        db=db
    )
