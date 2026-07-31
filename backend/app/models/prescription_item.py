import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import false
from sqlalchemy import func

from app.models.base import Base


class PrescriptionRecord(Base):
    """A signed, verifiable prescription.

    Distinct from the legacy single-medicine ``prescriptions`` table: this
    record carries many items, a cryptographic signature and a dispensing
    state, so a pharmacy can confirm the prescription is genuine, unexpired
    and not already filled before handing over medicine.
    """

    __tablename__ = "prescription_records"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    consultation_id = Column(
        String,
        ForeignKey("consultations.id"),
        nullable=True
    )

    appointment_id = Column(
        String,
        ForeignKey("appointments.id"),
        nullable=True
    )

    doctor_id = Column(
        String,
        ForeignKey("doctors.id"),
        nullable=False
    )

    patient_id = Column(
        String,
        ForeignKey("patients.id"),
        nullable=False
    )

    diagnosis = Column(
        String,
        nullable=True
    )

    advice = Column(
        Text,
        nullable=True
    )

    # Short human-quotable code printed on the prescription.
    verification_code = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    # HMAC over the clinical payload. Any edit invalidates it.
    signature = Column(
        String,
        nullable=False
    )

    issued_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    valid_until = Column(
        DateTime(timezone=True),
        nullable=False
    )

    status = Column(
        String,
        nullable=False,
        default="ACTIVE",
        server_default="ACTIVE",
    )

    dispensed_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    dispensed_by = Column(
        String,
        ForeignKey("users.id"),
        nullable=True
    )

    interaction_report = Column(
        JSON,
        nullable=True
    )

    is_cancelled = Column(
        Boolean,
        default=False,
        server_default=false(),
    )


class PrescriptionLine(Base):
    """One medicine on a prescription."""

    __tablename__ = "prescription_lines"

    sequence = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    id = Column(
        String,
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4())
    )

    prescription_id = Column(
        String,
        ForeignKey("prescription_records.id"),
        nullable=False,
        index=True
    )

    medicine_name = Column(
        String,
        nullable=False
    )

    generic_name = Column(
        String,
        nullable=True
    )

    strength = Column(
        String,
        nullable=True
    )

    dosage_form = Column(
        String,
        nullable=True
    )

    frequency = Column(
        String,
        nullable=False
    )

    duration = Column(
        String,
        nullable=False
    )

    route = Column(
        String,
        nullable=True
    )

    instructions = Column(
        Text,
        nullable=True
    )
