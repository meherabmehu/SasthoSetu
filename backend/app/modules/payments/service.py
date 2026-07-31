import secrets
from datetime import datetime, timezone

from fastapi import HTTPException

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.payment import Payment
from app.models.provider import LabOrder
from app.modules.notifications.service import create_notification
from app.payments.gateways import ChargeRequest, get_gateway

TERMINAL_STATUSES = {"COMPLETED", "REFUNDED", "FAILED", "CANCELLED"}


def _now():
    return datetime.now(timezone.utc)


def _reference() -> str:
    return f"SS{secrets.token_hex(7).upper()}"


def _payload(payment: Payment) -> dict:
    return {
        "id": payment.id,
        "reference": payment.reference,
        "purpose": payment.purpose,
        "amount_bdt": payment.amount_bdt,
        "platform_fee_bdt": payment.platform_fee_bdt,
        "payout_bdt": payment.payout_bdt,
        "method": payment.method,
        "status": payment.status,
        "gateway_reference": payment.gateway_reference,
        "refunded_amount_bdt": payment.refunded_amount_bdt,
        "failure_reason": payment.failure_reason,
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
        "completed_at": (
            payment.completed_at.isoformat() if payment.completed_at else None
        ),
    }


def _resolve_amount(payload, db: Session):
    """Derive the amount from the thing being paid for, never from the client."""
    if payload.purpose == "CONSULTATION":
        if not payload.appointment_id:
            raise HTTPException(
                status_code=400, detail="appointment_id is required"
            )
        appointment = (
            db.query(Appointment)
            .filter(Appointment.id == payload.appointment_id)
            .first()
        )
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")
        doctor = db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")
        return float(doctor.consultation_fee), None

    if payload.purpose == "LAB_ORDER":
        if not payload.lab_order_id:
            raise HTTPException(status_code=400, detail="lab_order_id is required")
        order = db.query(LabOrder).filter(LabOrder.id == payload.lab_order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Lab order not found")
        return float(order.price_bdt), order.provider_id

    raise HTTPException(status_code=400, detail="Unsupported payment purpose")


def create_checkout_service(payload, current_user, db: Session):
    """Start a payment. Repeating the same idempotency key returns the original."""
    existing = (
        db.query(Payment)
        .filter(Payment.idempotency_key == payload.idempotency_key)
        .first()
    )
    if existing:
        return _payload(existing)

    try:
        gateway = get_gateway(payload.method)
    except KeyError:
        raise HTTPException(
            status_code=400, detail=f"Unsupported payment method: {payload.method}"
        )

    amount, provider_id = _resolve_amount(payload, db)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Nothing to pay")

    commission = round(amount * settings.platform_commission_rate, 2)

    payment = Payment(
        reference=_reference(),
        idempotency_key=payload.idempotency_key,
        payer_user_id=current_user.get("user_id"),
        purpose=payload.purpose,
        appointment_id=payload.appointment_id,
        lab_order_id=payload.lab_order_id,
        provider_id=provider_id,
        amount_bdt=amount,
        platform_fee_bdt=commission,
        payout_bdt=round(amount - commission, 2),
        method=payload.method.lower(),
        status="PENDING",
    )

    result = gateway.initiate(
        ChargeRequest(
            reference=payment.reference,
            amount_bdt=amount,
            payer_msisdn=payload.payer_msisdn,
            description=payload.purpose,
        )
    )

    payment.gateway_reference = result.gateway_reference
    payment.gateway_payload = result.payload
    if not result.accepted:
        payment.status = "FAILED"
        payment.failure_reason = result.message

    db.add(payment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        duplicate = (
            db.query(Payment)
            .filter(Payment.idempotency_key == payload.idempotency_key)
            .first()
        )
        if duplicate:
            return _payload(duplicate)
        raise

    db.refresh(payment)
    response = _payload(payment)
    response["is_sandbox"] = result.is_sandbox
    response["gateway_message"] = result.message
    return response


def handle_callback_service(payload, db: Session):
    """Apply a gateway callback exactly once."""
    payment = (
        db.query(Payment)
        .filter(Payment.reference == payload.reference)
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    try:
        gateway = get_gateway(payment.method)
    except KeyError:
        raise HTTPException(status_code=400, detail="Unknown payment method")

    body = {
        "reference": payload.reference,
        "status": payload.status,
        "gateway_reference": payload.gateway_reference or "",
    }
    if not gateway.verify_callback(body, payload.signature):
        raise HTTPException(status_code=401, detail="Invalid callback signature")

    # Terminal payments are immutable: a replayed callback must not move money.
    if payment.status in TERMINAL_STATUSES:
        return _payload(payment)

    if payload.status.upper() == "COMPLETED":
        payment.status = "COMPLETED"
        payment.completed_at = _now()
        if payload.gateway_reference:
            payment.gateway_reference = payload.gateway_reference

        if payment.appointment_id:
            appointment = (
                db.query(Appointment)
                .filter(Appointment.id == payment.appointment_id)
                .first()
            )
            if appointment and appointment.status == "PENDING":
                appointment.status = "CONFIRMED"

        create_notification(
            user_id=payment.payer_user_id,
            title="Payment received",
            message=(
                f"Payment {payment.reference} of BDT "
                f"{payment.amount_bdt:.2f} was successful."
            ),
            db=db,
        )
    else:
        payment.status = "FAILED"
        payment.failure_reason = payload.failure_reason or "Declined by gateway"

    db.commit()
    db.refresh(payment)
    return _payload(payment)


def refund_service(payment_id: str, payload, current_user, db: Session):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.status != "COMPLETED":
        raise HTTPException(
            status_code=409, detail="Only a completed payment can be refunded"
        )

    remaining = round(payment.amount_bdt - payment.refunded_amount_bdt, 2)
    amount = payload.amount_bdt if payload.amount_bdt is not None else remaining

    if amount <= 0 or amount > remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Refund must be between 0 and {remaining}",
        )

    gateway = get_gateway(payment.method)
    result = gateway.refund(payment.gateway_reference or "", amount)
    if not result.accepted:
        raise HTTPException(status_code=502, detail=result.message)

    payment.refunded_amount_bdt = round(payment.refunded_amount_bdt + amount, 2)
    if payment.refunded_amount_bdt >= payment.amount_bdt:
        payment.status = "REFUNDED"

    create_notification(
        user_id=payment.payer_user_id,
        title="Refund issued",
        message=f"BDT {amount:.2f} was refunded for {payment.reference}.",
        db=db,
    )
    db.commit()
    db.refresh(payment)
    return _payload(payment)


def get_payment_service(payment_id: str, current_user, db: Session):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if (
        current_user.get("role") != "ADMIN"
        and payment.payer_user_id != current_user.get("user_id")
    ):
        raise HTTPException(status_code=403, detail="Not your payment")
    return _payload(payment)


def list_my_payments_service(current_user, db: Session, limit=50, offset=0):
    query = (
        db.query(Payment)
        .filter(Payment.payer_user_id == current_user.get("user_id"))
        .order_by(Payment.created_at.desc())
    )
    total = query.count()
    rows = query.offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_payload(row) for row in rows],
    }


def reconciliation_report_service(db: Session, provider_id: str | None = None):
    """Settlement summary: what was collected, kept and is owed to providers."""
    query = db.query(Payment).filter(Payment.status.in_(["COMPLETED", "REFUNDED"]))
    if provider_id:
        query = query.filter(Payment.provider_id == provider_id)

    totals = query.with_entities(
        func.coalesce(func.sum(Payment.amount_bdt), 0.0),
        func.coalesce(func.sum(Payment.platform_fee_bdt), 0.0),
        func.coalesce(func.sum(Payment.payout_bdt), 0.0),
        func.coalesce(func.sum(Payment.refunded_amount_bdt), 0.0),
        func.count(Payment.id),
    ).one()

    gross, fees, payouts, refunds, count = totals
    return {
        "transaction_count": int(count),
        "gross_collected_bdt": round(float(gross), 2),
        "platform_fees_bdt": round(float(fees), 2),
        "provider_payouts_bdt": round(float(payouts), 2),
        "refunded_bdt": round(float(refunds), 2),
        "net_settlement_bdt": round(float(gross) - float(refunds), 2),
        "commission_rate": settings.platform_commission_rate,
    }
