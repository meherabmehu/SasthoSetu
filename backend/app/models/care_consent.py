from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, true

from app.models.base import Base


class CareConsent(Base):
    __tablename__ = "patient_care_consents"

    patient_id = Column(String, ForeignKey("patients.id"), primary_key=True)
    doctor_id = Column(String, ForeignKey("doctors.id"), primary_key=True)
    granted = Column(Boolean, nullable=False, default=True, server_default=true())
    updated_at = Column(DateTime(timezone=True), nullable=False)
