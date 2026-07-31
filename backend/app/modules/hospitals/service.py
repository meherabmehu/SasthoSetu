from math import asin, cos, radians, sin, sqrt

from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.models.hospital import (
    BedStatusHistory,
    Hospital,
    HospitalStaff,
    Ward,
)

# Wards that can receive an emergency admission, in order of preference.
EMERGENCY_WARDS = ["emergency", "icu", "hdu", "general"]


def _distance_km(lat1, lon1, lat2, lon2):
    """Great-circle distance. Returns None when either point is unknown."""
    if None in (lat1, lon1, lat2, lon2):
        return None
    radius = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    return round(2 * radius * asin(sqrt(a)), 2)


def _ward_payload(ward: Ward) -> dict:
    available = max(0, ward.total_beds - ward.occupied_beds)
    rate = (ward.occupied_beds / ward.total_beds) if ward.total_beds else 0.0
    return {
        "id": ward.id,
        "ward_type": ward.ward_type,
        "name": ward.name,
        "total_beds": ward.total_beds,
        "occupied_beds": ward.occupied_beds,
        "available_beds": available,
        "occupancy_rate": round(rate, 3),
        "updated_at": ward.updated_at.isoformat() if ward.updated_at else None,
    }


def _hospital_payload(hospital: Hospital, wards: list[Ward]) -> dict:
    ward_payloads = [_ward_payload(w) for w in wards]
    return {
        "id": hospital.id,
        "code": hospital.code,
        "name": hospital.name,
        "district": hospital.district,
        "area": hospital.area,
        "address": hospital.address,
        "phone": hospital.phone,
        "latitude": hospital.latitude,
        "longitude": hospital.longitude,
        "has_emergency": bool(hospital.has_emergency),
        "is_active": bool(hospital.is_active),
        "wards": ward_payloads,
        "total_beds": sum(w["total_beds"] for w in ward_payloads),
        "available_beds": sum(w["available_beds"] for w in ward_payloads),
    }


def _get_hospital_or_404(hospital_id: str, db: Session) -> Hospital:
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        hospital = db.query(Hospital).filter(Hospital.code == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return hospital


def require_hospital_access(hospital_id: str, current_user: dict, db: Session):
    """Staff may only touch their own hospital; admins may touch any."""
    if current_user.get("role") == "ADMIN":
        return

    assignment = (
        db.query(HospitalStaff)
        .filter(
            HospitalStaff.hospital_id == hospital_id,
            HospitalStaff.user_id == current_user.get("user_id"),
            HospitalStaff.is_active.is_(True),
        )
        .first()
    )
    if not assignment:
        raise HTTPException(
            status_code=403,
            detail="You are not authorised to manage this hospital",
        )


def create_hospital_service(payload, db: Session):
    existing = db.query(Hospital).filter(Hospital.code == payload.code).first()
    if existing:
        raise HTTPException(
            status_code=409, detail="Hospital code already registered"
        )

    hospital = Hospital(
        code=payload.code,
        name=payload.name,
        district=payload.district,
        area=payload.area,
        address=payload.address,
        phone=payload.phone,
        latitude=payload.latitude,
        longitude=payload.longitude,
        has_emergency=payload.has_emergency,
    )
    db.add(hospital)
    db.commit()
    db.refresh(hospital)
    return _hospital_payload(hospital, [])


def update_hospital_service(hospital_id: str, payload, db: Session):
    hospital = _get_hospital_or_404(hospital_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(hospital, field, value)
    db.commit()
    db.refresh(hospital)
    wards = db.query(Ward).filter(Ward.hospital_id == hospital.id).all()
    return _hospital_payload(hospital, wards)


def list_hospitals_service(
    db: Session,
    district: str | None = None,
    emergency_only: bool = False,
    limit: int = 50,
    offset: int = 0,
):
    query = db.query(Hospital).filter(Hospital.is_active.is_(True))
    if district:
        query = query.filter(Hospital.district.ilike(district))
    if emergency_only:
        query = query.filter(Hospital.has_emergency.is_(True))

    total = query.count()
    hospitals = query.order_by(Hospital.name).offset(offset).limit(limit).all()

    items = []
    for hospital in hospitals:
        wards = db.query(Ward).filter(Ward.hospital_id == hospital.id).all()
        items.append(_hospital_payload(hospital, wards))

    return {"total": total, "limit": limit, "offset": offset, "items": items}


def get_hospital_service(hospital_id: str, db: Session):
    hospital = _get_hospital_or_404(hospital_id, db)
    wards = db.query(Ward).filter(Ward.hospital_id == hospital.id).all()
    return _hospital_payload(hospital, wards)


def create_ward_service(hospital_id: str, payload, current_user, db: Session):
    hospital = _get_hospital_or_404(hospital_id, db)
    require_hospital_access(hospital.id, current_user, db)

    if payload.occupied_beds > payload.total_beds:
        raise HTTPException(
            status_code=400, detail="Occupied beds cannot exceed total beds"
        )

    existing = (
        db.query(Ward)
        .filter(Ward.hospital_id == hospital.id, Ward.ward_type == payload.ward_type)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"A {payload.ward_type} ward already exists for this hospital",
        )

    ward = Ward(
        hospital_id=hospital.id,
        ward_type=payload.ward_type,
        name=payload.name,
        total_beds=payload.total_beds,
        occupied_beds=payload.occupied_beds,
    )
    db.add(ward)
    db.flush()

    db.add(
        BedStatusHistory(
            ward_id=ward.id,
            occupied_beds=ward.occupied_beds,
            total_beds=ward.total_beds,
            recorded_by=current_user.get("user_id"),
        )
    )
    db.commit()
    db.refresh(ward)
    return _ward_payload(ward)


def update_bed_status_service(ward_id: str, payload, current_user, db: Session):
    ward = db.query(Ward).filter(Ward.id == ward_id).first()
    if not ward:
        raise HTTPException(status_code=404, detail="Ward not found")

    require_hospital_access(ward.hospital_id, current_user, db)

    total = payload.total_beds if payload.total_beds is not None else ward.total_beds
    if payload.occupied_beds > total:
        raise HTTPException(
            status_code=400, detail="Occupied beds cannot exceed total beds"
        )

    ward.total_beds = total
    ward.occupied_beds = payload.occupied_beds

    db.add(
        BedStatusHistory(
            ward_id=ward.id,
            occupied_beds=ward.occupied_beds,
            total_beds=ward.total_beds,
            recorded_by=current_user.get("user_id"),
        )
    )
    db.commit()
    db.refresh(ward)
    return _ward_payload(ward)


def ward_history_service(ward_id: str, db: Session, limit: int = 100):
    ward = db.query(Ward).filter(Ward.id == ward_id).first()
    if not ward:
        raise HTTPException(status_code=404, detail="Ward not found")

    rows = (
        db.query(BedStatusHistory)
        .filter(BedStatusHistory.ward_id == ward_id)
        .order_by(BedStatusHistory.sequence.desc())
        .limit(min(limit, 500))
        .all()
    )
    return [
        {
            "occupied_beds": row.occupied_beds,
            "total_beds": row.total_beds,
            "available_beds": max(0, row.total_beds - row.occupied_beds),
            "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
        }
        for row in rows
    ]


def assign_staff_service(hospital_id: str, payload, db: Session):
    hospital = _get_hospital_or_404(hospital_id, db)

    existing = (
        db.query(HospitalStaff)
        .filter(
            HospitalStaff.hospital_id == hospital.id,
            HospitalStaff.user_id == payload.user_id,
        )
        .first()
    )
    if existing:
        existing.staff_role = payload.staff_role
        existing.is_active = True
        db.commit()
        return {"message": "Staff assignment updated"}

    db.add(
        HospitalStaff(
            hospital_id=hospital.id,
            user_id=payload.user_id,
            staff_role=payload.staff_role,
        )
    )
    db.commit()
    return {"message": "Staff assigned to hospital"}


def find_nearby_service(
    db: Session,
    latitude: float | None = None,
    longitude: float | None = None,
    district: str | None = None,
    ward_type: str | None = None,
    emergency: bool = False,
    require_bed: bool = True,
    limit: int = 10,
):
    """Find facilities that can actually accept the patient right now.

    Ranking is availability first, then distance: the nearest hospital is no
    use if it has no free bed of the type the patient needs.
    """
    query = db.query(Hospital).filter(Hospital.is_active.is_(True))
    if district:
        query = query.filter(Hospital.district.ilike(district))
    if emergency:
        query = query.filter(Hospital.has_emergency.is_(True))

    preferred = [ward_type] if ward_type else (EMERGENCY_WARDS if emergency else [])

    results = []
    for hospital in query.all():
        wards = db.query(Ward).filter(Ward.hospital_id == hospital.id).all()

        available_total = sum(max(0, w.total_beds - w.occupied_beds) for w in wards)
        icu_available = sum(
            max(0, w.total_beds - w.occupied_beds)
            for w in wards
            if w.ward_type == "icu"
        )

        matched_ward = None
        if preferred:
            for candidate in preferred:
                match = next(
                    (
                        w
                        for w in wards
                        if w.ward_type == candidate
                        and (w.total_beds - w.occupied_beds) > 0
                    ),
                    None,
                )
                if match:
                    matched_ward = match.ward_type
                    break
            if require_bed and matched_ward is None:
                continue
        elif require_bed and available_total <= 0:
            continue

        results.append(
            {
                "id": hospital.id,
                "code": hospital.code,
                "name": hospital.name,
                "district": hospital.district,
                "area": hospital.area,
                "phone": hospital.phone,
                "distance_km": _distance_km(
                    latitude, longitude, hospital.latitude, hospital.longitude
                ),
                "has_emergency": bool(hospital.has_emergency),
                "available_beds": available_total,
                "available_icu_beds": icu_available,
                "matched_ward": matched_ward,
            }
        )

    def sort_key(item):
        distance = item["distance_km"]
        return (
            0 if item["available_beds"] > 0 else 1,
            distance if distance is not None else 9_999,
            -item["available_beds"],
        )

    results.sort(key=sort_key)
    return results[:limit]
