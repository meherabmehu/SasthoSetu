from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.models.doctor_availability import DoctorAvailability
from app.modules.notifications.service import (
    create_notification
)


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

    if doctor.verification_status is False:
        raise HTTPException(
            status_code=403,
            detail="Doctor is not verified"
        )

    availability = (
        db.query(DoctorAvailability)
        .filter(
            DoctorAvailability.doctor_id
            == doctor.id,
            DoctorAvailability.available_date
            == str(payload.appointment_date),
            DoctorAvailability.start_time
            == payload.appointment_time,
            DoctorAvailability.is_booked
            == False
        )
        .first()
    )

    if not availability:
        raise HTTPException(
            status_code=400,
            detail="Selected slot not available"
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

    availability.is_booked = True

    db.add(appointment)
    db.commit()

    create_notification(
        user_id=patient.user_id,
        title="Appointment Booked",
        message=(
            f"Your appointment on "
            f"{appointment.appointment_date} "
            f"at {appointment.appointment_time} "
            f"has been booked."
        ),
        db=db
    )

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


def cancel_appointment_service(
    appointment_id: str,
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

    availability = (
        db.query(DoctorAvailability)
        .filter(
            DoctorAvailability.doctor_id
            == appointment.doctor_id,
            DoctorAvailability.available_date
            == appointment.appointment_date,
            DoctorAvailability.start_time
            == appointment.appointment_time
        )
        .first()
    )

    if availability:
        availability.is_booked = False

    appointment.status = "CANCELLED"


    db.commit()

    patient = (
        db.query(Patient)
        .filter(
            Patient.id == appointment.patient_id
        )
        .first()
    )

    if patient:
        create_notification(
            user_id=patient.user_id,
            title="Appointment Cancelled",
            message=(
                f"Your appointment on "
                f"{appointment.appointment_date} "
                f"at {appointment.appointment_time} "
                f"has been cancelled."
            ),
            db=db
        )

    return {
        "message": "Appointment cancelled successfully",
        "status": "CANCELLED"
    }
def reschedule_appointment_service(
    appointment_id: str,
    payload,
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

    if appointment.status == "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="Completed appointment cannot be rescheduled"
        )

    if appointment.status == "CANCELLED":
        raise HTTPException(
            status_code=400,
            detail="Cancelled appointment cannot be rescheduled"
        )

    old_slot = (
        db.query(DoctorAvailability)
        .filter(
            DoctorAvailability.doctor_id
            == appointment.doctor_id,
            DoctorAvailability.available_date
            == appointment.appointment_date,
            DoctorAvailability.start_time
            == appointment.appointment_time
        )
        .first()
    )

    if old_slot:
        old_slot.is_booked = False

    new_slot = (
        db.query(DoctorAvailability)
        .filter(
            DoctorAvailability.doctor_id
            == appointment.doctor_id,
            DoctorAvailability.available_date
            == str(payload.appointment_date),
            DoctorAvailability.start_time
            == payload.appointment_time,
            DoctorAvailability.is_booked
            == False
        )
        .first()
    )

    if not new_slot:
        raise HTTPException(
            status_code=400,
            detail="New slot not available"
        )

    new_slot.is_booked = True

    appointment.appointment_date = str(
        payload.appointment_date
    )

    appointment.appointment_time = (
        payload.appointment_time
    )

    db.commit()

    patient = (
        db.query(Patient)
        .filter(
            Patient.id == appointment.patient_id
        )
        .first()
    )

    if patient:
        create_notification(
            user_id=patient.user_id,
            title="Appointment Rescheduled",
            message=(
                f"Your appointment has been moved to "
                f"{appointment.appointment_date} "
                f"at {appointment.appointment_time}."
            ),
            db=db
        )

    return {
        "message": "Appointment rescheduled successfully"
    }