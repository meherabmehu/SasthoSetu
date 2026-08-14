from datetime import date

from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.models.doctor import Doctor
from app.models.doctor_availability import (
    DoctorAvailability
)


def upcoming_slots(query):
    """Restrict an availability query to today onwards.

    Slots are stored as ISO date strings, so a lexicographic comparison
    orders them correctly. Without this a doctor's calendar keeps offering
    dates that have already passed, and the first "next available" slot a
    patient is shown is one they can never attend.
    """

    return query.filter(
        DoctorAvailability.available_date >= date.today().isoformat()
    )


def assert_owns_calendar(
    doctor_id: str,
    current_user: dict,
    db: Session
) -> None:
    """Only the doctor themselves, or an administrator, may publish slots.

    A consulting calendar is the doctor's own commitment of time; letting any
    signed-in account write to it would let a stranger invent clinic hours.
    """

    if current_user.get("role") == "ADMIN":
        return

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

    if doctor.user_id != current_user.get("user_id"):
        raise HTTPException(
            status_code=403,
            detail="You cannot change another doctor's calendar"
        )


def create_availability_service(
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

    slot = DoctorAvailability(
        doctor_id=doctor_id,
        available_date=str(
            payload.available_date
        ),
        start_time=payload.start_time,
        end_time=payload.end_time
    )

    db.add(slot)
    db.commit()

    return {
        "message": "Availability slot created"
    }


def get_doctor_availability_service(
    doctor_id: str,
    db: Session
):

    return (
        upcoming_slots(
            db.query(DoctorAvailability)
            .filter(
                DoctorAvailability.doctor_id
                == doctor_id,
                DoctorAvailability.is_booked
                == False
            )
        )
        .order_by(
            DoctorAvailability.available_date.asc(),
            DoctorAvailability.start_time.asc()
        )
        .all()
    )