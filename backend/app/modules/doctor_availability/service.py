from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.models.doctor import Doctor
from app.models.doctor_availability import (
    DoctorAvailability
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
        db.query(DoctorAvailability)
        .filter(
            DoctorAvailability.doctor_id
            == doctor_id,
            DoctorAvailability.is_booked
            == False
        )
        .all()
    )