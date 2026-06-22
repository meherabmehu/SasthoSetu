from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.modules.notifications.service import (
    create_notification
)

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

    create_notification(
        user_id=patient.user_id,
        title="Medical Record Added",
        message=(
            "A new medical record has been "
            "added to your profile."
        ),
        db=db
    )

    return {
        "message": "Medical record created successfully"
    }

def get_patient_medical_records_service(
    patient_user_id: str,
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
            detail="Patient not found"
        )

    records = (
        db.query(MedicalRecord)
        .filter(
            MedicalRecord.patient_id == patient.id
        )
        .all()
    )

    return records


def get_doctor_medical_records_service(
    doctor_id: str,
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

    records = (
        db.query(MedicalRecord)
        .filter(
            MedicalRecord.doctor_id == doctor.id
        )
        .all()
    )

    return records