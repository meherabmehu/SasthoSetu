from fastapi import HTTPException

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.doctor import Doctor


def create_doctor_profile_service(
    user_id: str,
    payload,
    db: Session
):

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    existing_profile = (
        db.query(Doctor)
        .filter(
            Doctor.user_id == user_id
        )
        .first()
    )

    if existing_profile:
        raise HTTPException(
            status_code=409,
            detail="Doctor profile already exists"
        )

    try:

        doctor = Doctor(
            user_id=user_id,
            bmdc_number=payload.bmdc_number,
            specialization=payload.specialization,
            experience_years=payload.experience_years,
            consultation_fee=payload.consultation_fee,
            hospital_name=payload.hospital_name,
            bio=payload.bio,
            verification_status=False
        )

        db.add(doctor)
        db.commit()

        return {
            "message": "Doctor profile created",
            "verification_status": "PENDING"
        }

    except IntegrityError:

        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="BMDC number already exists"
        )


def get_all_doctors_service(
    db: Session
):
    return db.query(Doctor).all()


def get_doctor_by_id_service(
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

    return doctor


def get_doctors_by_specialization_service(
    specialization: str,
    db: Session
):

    doctors = (
        db.query(Doctor)
        .filter(
            Doctor.specialization == specialization
        )
        .all()
    )

    return doctors