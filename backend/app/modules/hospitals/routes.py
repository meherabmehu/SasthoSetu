from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query

from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import get_current_user, require_admin

from app.schemas.hospital import (
    BedStatusUpdate,
    HospitalCreate,
    HospitalUpdate,
    StaffAssign,
    WardCreate,
)

from app.modules.hospitals.service import (
    assign_staff_service,
    create_hospital_service,
    create_ward_service,
    find_nearby_service,
    get_hospital_service,
    list_hospitals_service,
    update_bed_status_service,
    update_hospital_service,
    ward_history_service,
)

router = APIRouter()


@router.post("/hospitals")
def create_hospital(
    payload: HospitalCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)
    return create_hospital_service(payload, db)


@router.get("/hospitals")
def list_hospitals(
    district: str | None = None,
    emergency_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return list_hospitals_service(
        db,
        district=district,
        emergency_only=emergency_only,
        limit=limit,
        offset=offset,
    )


@router.get("/hospitals/nearby")
def find_nearby_hospitals(
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    district: str | None = None,
    ward_type: str | None = None,
    emergency: bool = False,
    require_bed: bool = True,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return find_nearby_service(
        db,
        latitude=latitude,
        longitude=longitude,
        district=district,
        ward_type=ward_type,
        emergency=emergency,
        require_bed=require_bed,
        limit=limit,
    )


@router.get("/hospitals/{hospital_id}")
def get_hospital(hospital_id: str, db: Session = Depends(get_db)):
    return get_hospital_service(hospital_id, db)


@router.patch("/hospitals/{hospital_id}")
def update_hospital(
    hospital_id: str,
    payload: HospitalUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)
    return update_hospital_service(hospital_id, payload, db)


@router.post("/hospitals/{hospital_id}/wards")
def create_ward(
    hospital_id: str,
    payload: WardCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return create_ward_service(hospital_id, payload, current_user, db)


@router.patch("/wards/{ward_id}/bed-status")
def update_bed_status(
    ward_id: str,
    payload: BedStatusUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return update_bed_status_service(ward_id, payload, current_user, db)


@router.get("/wards/{ward_id}/history")
def ward_history(
    ward_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return ward_history_service(ward_id, db, limit=limit)


@router.post("/hospitals/{hospital_id}/staff")
def assign_staff(
    hospital_id: str,
    payload: StaffAssign,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)
    return assign_staff_service(hospital_id, payload, db)
