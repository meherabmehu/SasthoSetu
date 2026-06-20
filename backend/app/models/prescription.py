import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import ForeignKey

from app.models.base import Base


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    appointment_id = Column(
        String,
        ForeignKey("appointments.id"),
        nullable=False
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

    medicine_name = Column(
        String,
        nullable=False
    )

    dosage = Column(
        String,
        nullable=False
    )

    duration = Column(
        String,
        nullable=False
    )

    instructions = Column(
        String,
        nullable=True
    )