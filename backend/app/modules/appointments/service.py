from fastapi import HTTPException

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.models.doctor_availability import DoctorAvailability
from app.modules.notifications.service import (
    create_notification
)


def assert_appointment_access(
    appointment: Appointment,
    current_user: dict,
    db: Session
) -> None:
    """Allow the patient who owns the booking, the doctor seeing them, or an
    administrator.

    An appointment is jointly held: the patient may cancel or reschedule it and
    the treating doctor must be able to confirm or complete it, but no other
    account has any business touching it.
    """

    role = current_user.get("role")

    if role == "ADMIN":
        return

    user_id = current_user.get("user_id")

    if role == "DOCTOR":
        doctor = (
            db.query(Doctor)
            .filter(
                Doctor.id == appointment.doctor_id
            )
            .first()
        )

        if doctor and doctor.user_id == user_id:
            return

    patient = (
        db.query(Patient)
        .filter(
            Patient.id == appointment.patient_id
        )
        .first()
    )

    if patient and patient.user_id == user_id:
        return

    raise HTTPException(
        status_code=403,
        detail="You cannot access another patient's appointment"
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

    # Guard against double booking. The availability row is re-read with a
    # row lock so two concurrent requests for the same slot cannot both pass
    # the check above and each create an appointment.
    locked_slot = (
        db.query(DoctorAvailability)
        .filter(DoctorAvailability.id == availability.id)
        .with_for_update()
        .first()
    )

    if locked_slot is None or locked_slot.is_booked:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Selected slot was just booked by another patient"
        )

    clash = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date == str(payload.appointment_date),
            Appointment.appointment_time == payload.appointment_time,
            Appointment.status.notin_(["CANCELLED", "REJECTED"]),
        )
        .first()
    )

    if clash:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Doctor already has an appointment in this slot"
        )

    duplicate = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == patient.id,
            Appointment.appointment_date == str(payload.appointment_date),
            Appointment.appointment_time == payload.appointment_time,
            Appointment.status.notin_(["CANCELLED", "REJECTED"]),
        )
        .first()
    )

    if duplicate:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="You already have an appointment at this time"
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

    locked_slot.is_booked = True

    db.add(appointment)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Selected slot was just booked by another patient"
        )

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
    db: Session,
    current_user: dict
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

    assert_appointment_access(appointment, current_user, db)

    # Confirming or completing a visit is a clinical assertion about what
    # happened in the consulting room, so it belongs to the clinic rather than
    # the patient. A patient withdraws from a booking by cancelling it.
    if (
        current_user.get("role") == "PATIENT"
        and status != "CANCELLED"
    ):
        raise HTTPException(
            status_code=403,
            detail="Only the clinic can confirm or complete an appointment"
        )

    appointment.status = status

    db.commit()

    return {
        "message": "Appointment status updated",
        "new_status": status
    }


def cancel_appointment_service(
    appointment_id: str,
    db: Session,
    current_user: dict
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

    assert_appointment_access(appointment, current_user, db)

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
    db: Session,
    current_user: dict
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

    assert_appointment_access(appointment, current_user, db)

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