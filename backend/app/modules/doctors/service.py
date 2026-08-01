from fastapi import HTTPException

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.doctor import Doctor
from app.models.review import DoctorRatingSummary


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
        user.role = "DOCTOR"

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


def get_my_doctor_profile_service(
    current_user: dict,
    db: Session
):
    """Return the signed-in doctor's own profile.

    The portal needs the doctor row id, which is not the user id; without this
    it would have to download the whole directory to find one record.
    """

    doctor = (
        db.query(Doctor)
        .filter(
            Doctor.user_id == current_user.get("user_id")
        )
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Doctor profile not found"
        )

    return doctor


def get_doctor_by_id_service(
    doctor_id: str,
    db: Session
):
    """Public doctor profile.

    Returns the display name and rating alongside the profile row: a patient
    choosing a doctor needs the name and reputation, and the bare ORM row
    carries neither.
    """

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

    user = (
        db.query(User)
        .filter(
            User.id == doctor.user_id
        )
        .first()
    )

    summary = (
        db.query(DoctorRatingSummary)
        .filter(
            DoctorRatingSummary.doctor_id == doctor.id
        )
        .first()
    )

    return {
        "id": doctor.id,
        "user_id": doctor.user_id,
        "name": user.full_name if user else None,
        "bmdc_number": doctor.bmdc_number,
        "specialization": doctor.specialization,
        "experience_years": doctor.experience_years,
        "consultation_fee": doctor.consultation_fee,
        "hospital_name": doctor.hospital_name,
        "bio": doctor.bio,
        "verification_status": bool(doctor.verification_status),
        "rating": summary.average_rating if summary else None,
        "bayesian_rating": summary.bayesian_rating if summary else None,
        "review_count": summary.review_count if summary else 0,
    }


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


def get_pending_doctors_service(
    db: Session
):
    return (
        db.query(Doctor)
        .filter(
            Doctor.verification_status == False
        )
        .all()
    )


def verify_doctor_service(
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

    doctor.verification_status = True

    db.commit()

    return {
        "message": "Doctor verified successfully",
        "verification_status": True
    }