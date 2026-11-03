"""Patients explicitly grant or revoke record access for their treating doctors."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import get_current_user
from app.models.appointment import Appointment
from app.models.care_consent import CareConsent
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User

router = APIRouter()


class ConsentChoice(BaseModel):
    granted: bool


def _patient(user, db):
    patient = db.query(Patient).filter(Patient.user_id == user["user_id"]).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile required")
    return patient


@router.get("/patients/me/care-access")
def care_access(user=Depends(get_current_user), db: Session = Depends(get_db)):
    patient = _patient(user, db)
    rows = (db.query(Doctor, User.full_name).join(User, User.id == Doctor.user_id)
            .join(Appointment, Appointment.doctor_id == Doctor.id)
            .filter(Appointment.patient_id == patient.id,
                    Appointment.status.in_(["CONFIRMED", "IN_PROGRESS", "COMPLETED"]))
            .distinct().all())
    return [{"doctor_id": doctor.id, "doctor_name": name,
             "granted": bool((consent := db.get(CareConsent, (patient.id, doctor.id)))
                             and consent.granted)} for doctor, name in rows]


@router.put("/patients/me/care-access/{doctor_id}")
def set_care_access(doctor_id: str, payload: ConsentChoice,
                    user=Depends(get_current_user), db: Session = Depends(get_db)):
    patient = _patient(user, db)
    relationship = db.query(Appointment.id).filter(
        Appointment.patient_id == patient.id, Appointment.doctor_id == doctor_id,
        Appointment.status.in_(["CONFIRMED", "IN_PROGRESS", "COMPLETED"]),
    ).first()
    if not relationship:
        raise HTTPException(status_code=403, detail="No confirmed care relationship")
    consent = db.get(CareConsent, (patient.id, doctor_id))
    if not consent:
        consent = CareConsent(patient_id=patient.id, doctor_id=doctor_id)
        db.add(consent)
    consent.granted = payload.granted
    consent.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"doctor_id": doctor_id, "granted": consent.granted}
