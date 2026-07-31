import secrets
from datetime import datetime, timezone

from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.ai.drug_safety import normalize_drug
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.provider import LabOrder, LabTest, PharmacyStock, Provider

ACTIVE_ORDER_FLOW = {
    "REQUESTED": {"ACCEPTED", "CANCELLED"},
    "ACCEPTED": {"SAMPLE_COLLECTED", "CANCELLED"},
    "SAMPLE_COLLECTED": {"PROCESSING", "CANCELLED"},
    "PROCESSING": {"CANCELLED"},
}


def _now():
    return datetime.now(timezone.utc)


def _provider_or_404(provider_id: str, db: Session) -> Provider:
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if not provider:
        provider = db.query(Provider).filter(Provider.code == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


def require_provider_access(provider: Provider, current_user, db: Session):
    if current_user.get("role") == "ADMIN":
        return
    if provider.owner_user_id and provider.owner_user_id == current_user.get("user_id"):
        return
    raise HTTPException(
        status_code=403, detail="You are not authorised to manage this provider"
    )


def _provider_payload(provider: Provider) -> dict:
    return {
        "id": provider.id,
        "code": provider.code,
        "name": provider.name,
        "provider_type": provider.provider_type,
        "district": provider.district,
        "area": provider.area,
        "address": provider.address,
        "phone": provider.phone,
        "licence_number": provider.licence_number,
        "latitude": provider.latitude,
        "longitude": provider.longitude,
        "is_verified": bool(provider.is_verified),
        "is_active": bool(provider.is_active),
    }


def create_provider_service(payload, db: Session):
    if db.query(Provider).filter(Provider.code == payload.code).first():
        raise HTTPException(status_code=409, detail="Provider code already exists")

    provider = Provider(**payload.model_dump())
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return _provider_payload(provider)


def verify_provider_service(provider_id: str, db: Session):
    provider = _provider_or_404(provider_id, db)
    provider.is_verified = True
    db.commit()
    db.refresh(provider)
    return _provider_payload(provider)


def list_providers_service(
    db: Session,
    provider_type: str | None = None,
    district: str | None = None,
    verified_only: bool = False,
    limit: int = 50,
    offset: int = 0,
):
    query = db.query(Provider).filter(Provider.is_active.is_(True))
    if provider_type:
        query = query.filter(Provider.provider_type == provider_type.upper())
    if district:
        query = query.filter(Provider.district.ilike(district))
    if verified_only:
        query = query.filter(Provider.is_verified.is_(True))

    total = query.count()
    rows = query.order_by(Provider.name).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_provider_payload(row) for row in rows],
    }


def add_lab_test_service(provider_id: str, payload, current_user, db: Session):
    provider = _provider_or_404(provider_id, db)
    require_provider_access(provider, current_user, db)

    if provider.provider_type != "LAB":
        raise HTTPException(status_code=400, detail="Provider is not a lab")

    existing = (
        db.query(LabTest)
        .filter(LabTest.provider_id == provider.id, LabTest.code == payload.code)
        .first()
    )
    if existing:
        for field, value in payload.model_dump().items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        test = existing
    else:
        test = LabTest(provider_id=provider.id, **payload.model_dump())
        db.add(test)
        db.commit()
        db.refresh(test)

    return {
        "id": test.id,
        "code": test.code,
        "name": test.name,
        "sample_type": test.sample_type,
        "price_bdt": test.price_bdt,
        "turnaround_hours": test.turnaround_hours,
    }


def list_lab_tests_service(db: Session, provider_id: str | None = None, search: str | None = None):
    query = db.query(LabTest).filter(LabTest.is_active.is_(True))
    if provider_id:
        provider = _provider_or_404(provider_id, db)
        query = query.filter(LabTest.provider_id == provider.id)
    if search:
        query = query.filter(LabTest.name.ilike(f"%{search}%"))

    rows = query.order_by(LabTest.price_bdt.asc()).limit(200).all()
    return [
        {
            "id": row.id,
            "provider_id": row.provider_id,
            "code": row.code,
            "name": row.name,
            "sample_type": row.sample_type,
            "price_bdt": row.price_bdt,
            "turnaround_hours": row.turnaround_hours,
        }
        for row in rows
    ]


def _order_payload(order: LabOrder, db: Session, include_result=True) -> dict:
    test = db.query(LabTest).filter(LabTest.id == order.lab_test_id).first()
    payload = {
        "id": order.id,
        "order_code": order.order_code,
        "provider_id": order.provider_id,
        "test_name": test.name if test else None,
        "status": order.status,
        "price_bdt": order.price_bdt,
        "share_with_doctor": bool(order.share_with_doctor),
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "collected_at": (
            order.collected_at.isoformat() if order.collected_at else None
        ),
        "reported_at": order.reported_at.isoformat() if order.reported_at else None,
    }
    if include_result and order.status == "REPORTED":
        payload["result_summary"] = order.result_summary
        payload["result_values"] = order.result_values
        payload["is_abnormal"] = bool(order.is_abnormal)
        payload["result_file_id"] = order.result_file_id
    return payload


def create_lab_order_service(payload, current_user, db: Session):
    provider = _provider_or_404(payload.provider_id, db)
    if not provider.is_verified:
        raise HTTPException(
            status_code=400, detail="Provider is not verified for order routing"
        )

    test = (
        db.query(LabTest)
        .filter(LabTest.id == payload.lab_test_id, LabTest.provider_id == provider.id)
        .first()
    )
    if not test:
        raise HTTPException(
            status_code=404, detail="Test not found for this provider"
        )

    target_user_id = payload.patient_user_id or current_user.get("user_id")
    if (
        target_user_id != current_user.get("user_id")
        and current_user.get("role") not in ("ADMIN", "DOCTOR")
    ):
        raise HTTPException(
            status_code=403, detail="Cannot order a test for another patient"
        )

    patient = db.query(Patient).filter(Patient.user_id == target_user_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    doctor = (
        db.query(Doctor).filter(Doctor.user_id == current_user.get("user_id")).first()
    )

    order = LabOrder(
        order_code=f"LAB-{secrets.token_hex(5).upper()}",
        provider_id=provider.id,
        lab_test_id=test.id,
        patient_id=patient.id,
        ordered_by_doctor_id=doctor.id if doctor else None,
        consultation_id=payload.consultation_id,
        price_bdt=test.price_bdt,
        share_with_doctor=payload.share_with_doctor,
        status="REQUESTED",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return _order_payload(order, db)


def _order_or_404(order_id: str, db: Session) -> LabOrder:
    order = db.query(LabOrder).filter(LabOrder.id == order_id).first()
    if not order:
        order = db.query(LabOrder).filter(LabOrder.order_code == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Lab order not found")
    return order


def update_order_status_service(order_id: str, payload, current_user, db: Session):
    order = _order_or_404(order_id, db)
    provider = _provider_or_404(order.provider_id, db)
    require_provider_access(provider, current_user, db)

    allowed = ACTIVE_ORDER_FLOW.get(order.status, set())
    if payload.status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot move an order from {order.status} to {payload.status}",
        )

    order.status = payload.status
    if payload.status == "SAMPLE_COLLECTED":
        order.collected_at = _now()

    db.commit()
    db.refresh(order)
    return _order_payload(order, db)


def upload_result_service(order_id: str, payload, current_user, db: Session):
    order = _order_or_404(order_id, db)
    provider = _provider_or_404(order.provider_id, db)
    require_provider_access(provider, current_user, db)

    if order.status in ("REPORTED", "CANCELLED"):
        raise HTTPException(
            status_code=409, detail=f"Order is already {order.status}"
        )

    order.result_summary = payload.result_summary
    order.result_values = payload.result_values
    order.is_abnormal = payload.is_abnormal
    order.result_file_id = payload.result_file_id
    order.status = "REPORTED"
    order.reported_at = _now()

    patient = db.query(Patient).filter(Patient.id == order.patient_id).first()
    if patient:
        from app.modules.notifications.service import create_notification

        create_notification(
            user_id=patient.user_id,
            title="Lab result ready",
            message=(
                f"Your result for order {order.order_code} is available."
                + (" Please review it with your doctor." if payload.is_abnormal else "")
            ),
            db=db,
        )

    db.commit()
    db.refresh(order)
    return _order_payload(order, db)


def get_order_service(order_id: str, current_user, db: Session):
    """Return an order, enforcing the patient's sharing consent."""
    order = _order_or_404(order_id, db)
    role = current_user.get("role")
    user_id = current_user.get("user_id")

    patient = db.query(Patient).filter(Patient.id == order.patient_id).first()
    is_patient = patient and patient.user_id == user_id

    provider = db.query(Provider).filter(Provider.id == order.provider_id).first()
    is_provider = provider and provider.owner_user_id == user_id

    doctor = db.query(Doctor).filter(Doctor.user_id == user_id).first()
    is_ordering_doctor = doctor and doctor.id == order.ordered_by_doctor_id

    if role == "ADMIN" or is_patient or is_provider:
        return _order_payload(order, db)

    if is_ordering_doctor:
        if not order.share_with_doctor:
            raise HTTPException(
                status_code=403,
                detail="The patient has not shared this result",
            )
        return _order_payload(order, db)

    raise HTTPException(status_code=403, detail="Not authorised to view this order")


def set_consent_service(order_id: str, payload, current_user, db: Session):
    order = _order_or_404(order_id, db)
    patient = db.query(Patient).filter(Patient.id == order.patient_id).first()
    if not patient or patient.user_id != current_user.get("user_id"):
        raise HTTPException(
            status_code=403, detail="Only the patient can change sharing consent"
        )

    order.share_with_doctor = payload.share_with_doctor
    db.commit()
    db.refresh(order)
    return _order_payload(order, db)


def list_patient_orders_service(patient_user_id: str, current_user, db: Session):
    if (
        current_user.get("user_id") != patient_user_id
        and current_user.get("role") != "ADMIN"
    ):
        raise HTTPException(status_code=403, detail="Not authorised")

    patient = db.query(Patient).filter(Patient.user_id == patient_user_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    rows = (
        db.query(LabOrder)
        .filter(LabOrder.patient_id == patient.id)
        .order_by(LabOrder.created_at.desc())
        .all()
    )
    return [_order_payload(row, db) for row in rows]


def list_provider_orders_service(provider_id: str, current_user, db: Session):
    provider = _provider_or_404(provider_id, db)
    require_provider_access(provider, current_user, db)

    rows = (
        db.query(LabOrder)
        .filter(LabOrder.provider_id == provider.id)
        .order_by(LabOrder.created_at.desc())
        .all()
    )
    return [_order_payload(row, db) for row in rows]


def upsert_stock_service(provider_id: str, payload, current_user, db: Session):
    provider = _provider_or_404(provider_id, db)
    require_provider_access(provider, current_user, db)

    if provider.provider_type != "PHARMACY":
        raise HTTPException(status_code=400, detail="Provider is not a pharmacy")

    generic = normalize_drug(payload.brand_name)
    existing = (
        db.query(PharmacyStock)
        .filter(
            PharmacyStock.provider_id == provider.id,
            PharmacyStock.generic_name == generic,
            PharmacyStock.strength == payload.strength,
        )
        .first()
    )

    if existing:
        existing.brand_name = payload.brand_name
        existing.unit_price_bdt = payload.unit_price_bdt
        existing.quantity_available = payload.quantity_available
        item = existing
    else:
        item = PharmacyStock(
            provider_id=provider.id,
            brand_name=payload.brand_name,
            generic_name=generic,
            strength=payload.strength,
            unit_price_bdt=payload.unit_price_bdt,
            quantity_available=payload.quantity_available,
        )
        db.add(item)

    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "brand_name": item.brand_name,
        "generic_name": item.generic_name,
        "strength": item.strength,
        "unit_price_bdt": item.unit_price_bdt,
        "quantity_available": item.quantity_available,
    }


def search_stock_service(db: Session, medicine: str, district: str | None = None):
    """Find pharmacies holding a medicine, matched on generic name.

    Searching by generic rather than brand is what makes this useful: a patient
    holding a prescription for one brand can be pointed at any equivalent.
    """
    generic = normalize_drug(medicine)

    query = (
        db.query(PharmacyStock, Provider)
        .join(Provider, Provider.id == PharmacyStock.provider_id)
        .filter(
            PharmacyStock.generic_name == generic,
            PharmacyStock.quantity_available > 0,
            Provider.is_active.is_(True),
        )
    )
    if district:
        query = query.filter(Provider.district.ilike(district))

    rows = query.order_by(PharmacyStock.unit_price_bdt.asc()).limit(50).all()
    return {
        "searched_for": medicine,
        "resolved_generic": generic,
        "results": [
            {
                "provider_id": provider.id,
                "provider_name": provider.name,
                "district": provider.district,
                "area": provider.area,
                "phone": provider.phone,
                "is_verified": bool(provider.is_verified),
                "brand_name": stock.brand_name,
                "strength": stock.strength,
                "unit_price_bdt": stock.unit_price_bdt,
                "quantity_available": stock.quantity_available,
            }
            for stock, provider in rows
        ],
    }
