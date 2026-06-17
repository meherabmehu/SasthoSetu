from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.appointment import Appointment


def create_appointment_service(
    patient_user_id: str,
    payload,
    db: Session
):

    patient = (
        db.query(Patient)
        .filter(
            Patient.user_id == patient_user_id
        )
        .first()
    )

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient profile not found"
        )

    doctor = (
        db.query(Doctor)
        .filter(
            Doctor.id == payload.doctor_id
        )
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Doctor not found"
        )

    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=str(
            payload.appointment_date
        ),
        appointment_time=payload.appointment_time,
        reason=payload.reason,
        status="PENDING"
    )

    db.add(appointment)
    db.commit()

    return {
        "message": "Appointment created",
        "status": "PENDING"
    }