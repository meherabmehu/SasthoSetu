from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.patient import Patient


def create_patient_profile_service(
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
        db.query(Patient)
        .filter(
            Patient.user_id == user_id
        )
        .first()
    )

    if existing_profile:
        raise HTTPException(
            status_code=409,
            detail="Patient profile already exists"
        )

    patient = Patient(
        user_id=user_id,
        date_of_birth=payload.date_of_birth,
        gender=payload.gender,
        blood_group=payload.blood_group,
        height_cm=payload.height_cm,
        weight_kg=payload.weight_kg,
        emergency_contact=payload.emergency_contact,
        address=payload.address
    )

    db.add(patient)
    db.commit()

    return {
        "message": "Patient profile created successfully"
    }


def get_patient_profile_service(
    user_id: str,
    db: Session
):

    patient = (
        db.query(Patient)
        .filter(
            Patient.user_id == user_id
        )
        .first()
    )

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient profile not found"
        )

    return patient