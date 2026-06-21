from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord


def create_medical_record_service(
    doctor_id: str,
    payload,
    db: Session
):

    doctor = (
        db.query(Doctor)
        .filter(
            Doctor.id == doctor_id
        )
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Doctor not found"
        )

    patient = (
        db.query(Patient)
        .filter(
            Patient.id == payload.patient_id
        )
        .first()
    )

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found"
        )

    record = MedicalRecord(
        patient_id=payload.patient_id,
        doctor_id=doctor_id,
        diagnosis=payload.diagnosis,
        notes=payload.notes,
        record_date=str(payload.record_date)
    )

    db.add(record)
    db.commit()

    return {
        "message": "Medical record created successfully"
    }