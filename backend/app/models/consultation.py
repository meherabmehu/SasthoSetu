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


class Consultation(Base):
    """A clinical encounter attached to an appointment."""

    __tablename__ = "consultations"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    appointment_id = Column(
        String,
        ForeignKey("appointments.id"),
        nullable=False,
        unique=True
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

    triage_session_id = Column(
        String,
        ForeignKey("triage_sessions.id"),
        nullable=True
    )

    status = Column(
        String,
        nullable=False,
        default="OPEN",
        server_default="OPEN",
    )

    chief_complaint = Column(
        Text,
        nullable=True
    )

    examination_notes = Column(
        Text,
        nullable=True
    )

    diagnosis = Column(
        String,
        nullable=True
    )

    advice = Column(
        Text,
        nullable=True
    )

    follow_up_date = Column(
        String,
        nullable=True
    )

    investigations = Column(
        JSON,
        nullable=True
    )

    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    closed_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    # Once signed the record becomes append-only; corrections are added as
    # amendments rather than edits, which is what a clinical audit requires.
    is_signed = Column(
        Boolean,
        default=False,
        server_default=false(),
    )


class ConsultationMessage(Base):
    """Secure message exchanged inside a consultation."""

    __tablename__ = "consultation_messages"

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

    consultation_id = Column(
        String,
        ForeignKey("consultations.id"),
        nullable=False,
        index=True
    )

    sender_user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=False
    )

    sender_role = Column(
        String,
        nullable=False
    )

    body = Column(
        Text,
        nullable=False
    )

    sent_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
