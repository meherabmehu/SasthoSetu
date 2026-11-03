from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Literal
from app.models.payment import Payment
from app.payments.gateways import get_gateway

from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import get_current_user, require_admin

from app.payments.gateways import SUPPORTED_METHODS
from app.schemas.provider import (
    CheckoutRequest,
    PaymentCallback,
    RefundRequest,
)

from app.modules.payments.service import (
    create_checkout_service,
    get_payment_service,
    handle_callback_service,
    list_my_payments_service,
    reconciliation_report_service,
    refund_service,
)

router = APIRouter()


@router.get("/payments/methods")
def list_methods():
    return {"methods": SUPPORTED_METHODS, "currency": "BDT", "is_sandbox": True, "mode": "demo"}


class SimulationResult(BaseModel):
    status: Literal["COMPLETED", "FAILED"]


@router.post("/payments/{payment_id}/simulate")
def simulate_payment(payment_id: str, payload: SimulationResult,
                     current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Local simulator only. Never contacts a provider or moves money."""
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.payer_user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your payment")
    body = {"reference": payment.reference, "status": payload.status,
            "gateway_reference": payment.gateway_reference or ""}
    callback = PaymentCallback(**body, signature=get_gateway(payment.method).signature_for(body))
    return handle_callback_service(callback, db)


@router.post("/payments/checkout")
def create_checkout(
    payload: CheckoutRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a payment. Reusing an idempotency key returns the original charge."""
    return create_checkout_service(payload, current_user, db)


@router.post("/payments/callback")
def payment_callback(
    payload: PaymentCallback,
    db: Session = Depends(get_db),
):
    """Gateway webhook. Signature-verified and safe to replay."""
    return handle_callback_service(payload, db)


@router.get("/payments/mine")
def list_my_payments(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_my_payments_service(current_user, db, limit=limit, offset=offset)


@router.get("/payments/reconciliation")
def reconciliation_report(
    provider_id: str | None = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)
    return reconciliation_report_service(db, provider_id=provider_id)


@router.get("/payments/{payment_id}")
def get_payment(
    payment_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_payment_service(payment_id, current_user, db)


@router.post("/payments/{payment_id}/refund")
def refund_payment(
    payment_id: str,
    payload: RefundRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)
    return refund_service(payment_id, payload, current_user, db)
