from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.prescription import Prescription


def create_prescription_service(
    doctor_id: str,
    payload,
    db: Session
):

    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == payload.appointment_id
        )
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    prescription = Prescription(
        appointment_id=appointment.id,
        doctor_id=doctor_id,
        patient_id=appointment.patient_id,
        medicine_name=payload.medicine_name,
        dosage=payload.dosage,
        duration=payload.duration,
        instructions=payload.instructions
    )

    db.add(prescription)
    db.commit()

    return {
        "message": "Prescription created successfully"
    }