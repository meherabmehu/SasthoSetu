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

def get_patient_appointments_service(
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
            detail="Patient profile not found"
        )

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == patient.id
        )
        .all()
    )

    return appointments

def get_doctor_appointments_service(
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

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor.id
        )
        .all()
    )

    return appointments
def update_appointment_status_service(
    appointment_id: str,
    status: str,
    db: Session
):

    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id
        )
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    appointment.status = status

    db.commit()

    return {
        "message": "Appointment status updated",
        "new_status": status
    }