import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Float
from sqlalchemy import Text
from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import false
from sqlalchemy import func

from app.models.base import Base


class Payment(Base):
    """A payment for a consultation, lab order or pharmacy fulfilment.

    Every money movement is recorded here with an idempotency key so a retried
    request or a repeated gateway callback can never charge or credit twice.
    """

    __tablename__ = "payments"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    reference = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    idempotency_key = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    payer_user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    purpose = Column(
        String,
        nullable=False
    )

    appointment_id = Column(
        String,
        ForeignKey("appointments.id"),
        nullable=True
    )

    lab_order_id = Column(
        String,
        ForeignKey("lab_orders.id"),
        nullable=True
    )

    provider_id = Column(
        String,
        ForeignKey("providers.id"),
        nullable=True
    )

    amount_bdt = Column(
        Float,
        nullable=False
    )

    platform_fee_bdt = Column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )

    payout_bdt = Column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )

    method = Column(
        String,
        nullable=False
    )

    status = Column(
        String,
        nullable=False,
        default="PENDING",
        server_default="PENDING",
    )

    gateway_reference = Column(
        String,
        nullable=True
    )

    gateway_payload = Column(
        JSON,
        nullable=True
    )

    failure_reason = Column(
        Text,
        nullable=True
    )

    refunded_amount_bdt = Column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )

    is_reconciled = Column(
        Boolean,
        default=False,
        server_default=false(),
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    completed_at = Column(
        DateTime(timezone=True),
        nullable=True
    )
