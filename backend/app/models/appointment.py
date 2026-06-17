import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import ForeignKey

from app.models.base import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    patient_id = Column(
        String,
        ForeignKey("patients.id"),
        nullable=False
    )

    doctor_id = Column(
        String,
        ForeignKey("doctors.id"),
        nullable=False
    )

    appointment_date = Column(
        String,
        nullable=False
    )

    appointment_time = Column(
        String,
        nullable=False
    )

    reason = Column(
        String,
        nullable=False
    )

    status = Column(
        String,
        nullable=False,
        default="PENDING"
    )