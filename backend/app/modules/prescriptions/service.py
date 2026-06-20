from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.prescription import Prescription
from app.models.patient import Patient
from app.models.doctor import Doctor


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

    if appointment.status != "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="Appointment not completed"
        )

    if appointment.doctor_id != doctor_id:
        raise HTTPException(
            status_code=403,
            detail="Unauthorized doctor"
        )

    existing_prescription = (
        db.query(Prescription)
        .filter(
            Prescription.appointment_id == appointment.id
        )
        .first()
    )

    if existing_prescription:
        raise HTTPException(
            status_code=409,
            detail="Prescription already exists"
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
def get_patient_prescriptions_service(
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

    prescriptions = (
        db.query(Prescription)
        .filter(
            Prescription.patient_id == patient.id
        )
        .all()
    )

    return prescriptions


def get_doctor_prescriptions_service(
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

    prescriptions = (
        db.query(Prescription)
        .filter(
            Prescription.doctor_id == doctor.id
        )
        .all()
    )

    return prescriptions