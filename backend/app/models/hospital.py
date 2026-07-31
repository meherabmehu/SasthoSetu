import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Integer
from sqlalchemy import Float
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import false
from sqlalchemy import true
from sqlalchemy import func
from sqlalchemy import Index
from sqlalchemy import UniqueConstraint

from app.models.base import Base


class Hospital(Base):
    __tablename__ = "hospitals"

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

    latitude = Column(
        Float,
        nullable=True
    )

    longitude = Column(
        Float,
        nullable=True
    )

    has_emergency = Column(
        Boolean,
        default=True,
        server_default=true(),
    )

    is_active = Column(
        Boolean,
        default=True,
        server_default=true(),
    )


class Ward(Base):
    __tablename__ = "wards"

    __table_args__ = (
        UniqueConstraint(
            "hospital_id", "ward_type", name="uq_ward_type_per_hospital"
        ),
    )

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    hospital_id = Column(
        String,
        ForeignKey("hospitals.id"),
        nullable=False
    )

    ward_type = Column(
        String,
        nullable=False
    )

    name = Column(
        String,
        nullable=False
    )

    total_beds = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    occupied_beds = Column(
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


class HospitalStaff(Base):
    """Links a user account to the hospital whose capacity they may update."""

    __tablename__ = "hospital_staff"

    __table_args__ = (
        UniqueConstraint("hospital_id", "user_id", name="uq_staff_per_hospital"),
    )

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    hospital_id = Column(
        String,
        ForeignKey("hospitals.id"),
        nullable=False
    )

    user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=False
    )

    staff_role = Column(
        String,
        nullable=False,
        default="WARD_MANAGER",
        server_default="WARD_MANAGER",
    )

    is_active = Column(
        Boolean,
        default=True,
        server_default=true(),
    )


class BedStatusHistory(Base):
    """Append-only record of every capacity change, for audit and analytics."""

    __tablename__ = "bed_status_history"

    __table_args__ = (
        Index("ix_bed_history_ward_time", "ward_id", "sequence"),
    )

    id = Column(
        String,
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4())
    )

    # Monotonic counter. Timestamps alone are not enough to order two updates
    # recorded inside the same clock tick.
    sequence = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    ward_id = Column(
        String,
        ForeignKey("wards.id"),
        nullable=False
    )

    occupied_beds = Column(
        Integer,
        nullable=False
    )

    total_beds = Column(
        Integer,
        nullable=False
    )

    recorded_by = Column(
        String,
        ForeignKey("users.id"),
        nullable=True
    )

    recorded_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    is_synthetic = Column(
        Boolean,
        default=False,
        server_default=false(),
    )
