import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import ForeignKey

from app.models.base import Base


class MedicalRecord(Base):
    __tablename__ = "medical_records"

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

    diagnosis = Column(
        String,
        nullable=False
    )

    notes = Column(
        String,
        nullable=True
    )

    record_date = Column(
        String,
        nullable=False
    )