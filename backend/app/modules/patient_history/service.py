from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.prescription import Prescription
from app.models.medical_record import MedicalRecord


def get_patient_history_service(
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

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == patient.id
        )
        .all()
    )

    prescriptions = (
        db.query(Prescription)
        .filter(
            Prescription.patient_id == patient.id
        )
        .all()
    )

    medical_records = (
        db.query(MedicalRecord)
        .filter(
            MedicalRecord.patient_id == patient.id
        )
        .all()
    )

    return {
        "patient": patient,
        "appointments": appointments,
        "prescriptions": prescriptions,
        "medical_records": medical_records
    }