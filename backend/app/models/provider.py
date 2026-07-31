import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Integer
from sqlalchemy import Float
from sqlalchemy import Text
from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import UniqueConstraint
from sqlalchemy import false
from sqlalchemy import true
from sqlalchemy import func

from app.models.base import Base


class Provider(Base):
    """A diagnostic lab or pharmacy on the platform."""

    __tablename__ = "providers"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    code = Column(
        String,
        unique=True,
        nullable=False
    )

    name = Column(
        String,
        nullable=False
    )

    provider_type = Column(
        String,
        nullable=False,
        index=True
    )

    district = Column(
        String,
        nullable=False,
        index=True
    )

    area = Column(
        String,
        nullable=True
    )

    address = Column(
        String,
        nullable=True
    )

    phone = Column(
        String,
        nullable=True
    )

    licence_number = Column(
        String,
        nullable=True
    )

    latitude = Column(
        Float,
        nullable=True
    )

    longitude = Column(
        Float,
        nullable=True
    )

    is_verified = Column(
        Boolean,
        default=False,
        server_default=false(),
    )

    is_active = Column(
        Boolean,
        default=True,
        server_default=true(),
    )

    owner_user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=True
    )


class LabTest(Base):
    """A test offered by a lab, with its price."""

    __tablename__ = "lab_tests"

    __table_args__ = (
        UniqueConstraint("provider_id", "code", name="uq_test_code_per_provider"),
    )

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    provider_id = Column(
        String,
        ForeignKey("providers.id"),
        nullable=False,
        index=True
    )

    code = Column(
        String,
        nullable=False
    )

    name = Column(
        String,
        nullable=False
    )

    sample_type = Column(
        String,
        nullable=True
    )

    price_bdt = Column(
        Float,
        nullable=False
    )

    turnaround_hours = Column(
        Integer,
        nullable=True
    )

    is_active = Column(
        Boolean,
        default=True,
        server_default=true(),
    )


class LabOrder(Base):
    """An ordered test, tracked from request through to result."""

    __tablename__ = "lab_orders"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    order_code = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    provider_id = Column(
        String,
        ForeignKey("providers.id"),
        nullable=False,
        index=True
    )

    lab_test_id = Column(
        String,
        ForeignKey("lab_tests.id"),
        nullable=False
    )

    patient_id = Column(
        String,
        ForeignKey("patients.id"),
        nullable=False,
        index=True
    )

    ordered_by_doctor_id = Column(
        String,
        ForeignKey("doctors.id"),
        nullable=True
    )

    consultation_id = Column(
        String,
        ForeignKey("consultations.id"),
        nullable=True
    )

    status = Column(
        String,
        nullable=False,
        default="REQUESTED",
        server_default="REQUESTED",
    )

    price_bdt = Column(
        Float,
        nullable=False
    )

    # Patient consent is explicit: a result is only visible to the ordering
    # clinician when the patient has agreed to share it.
    share_with_doctor = Column(
        Boolean,
        default=True,
        server_default=true(),
    )

    result_summary = Column(
        Text,
        nullable=True
    )

    result_values = Column(
        JSON,
        nullable=True
    )

    result_file_id = Column(
        String,
        nullable=True
    )

    is_abnormal = Column(
        Boolean,
        default=False,
        server_default=false(),
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    collected_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    reported_at = Column(
        DateTime(timezone=True),
        nullable=True
    )


class PharmacyStock(Base):
    """Medicine availability at a pharmacy."""

    __tablename__ = "pharmacy_stock"

    __table_args__ = (
        UniqueConstraint(
            "provider_id", "generic_name", "strength",
            name="uq_stock_item_per_provider",
        ),
    )

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    provider_id = Column(
        String,
        ForeignKey("providers.id"),
        nullable=False,
        index=True
    )

    brand_name = Column(
        String,
        nullable=False
    )

    generic_name = Column(
        String,
        nullable=False,
        index=True
    )

    strength = Column(
        String,
        nullable=True
    )

    unit_price_bdt = Column(
        Float,
        nullable=False
    )

    quantity_available = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=func.now(),
        server_default=func.now(),
    )
