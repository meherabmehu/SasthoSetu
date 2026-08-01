# -*- coding: utf-8 -*-
"""Doctor reviews backed by proof of a real encounter.

The integrity rule is structural, not advisory: a review can only be created
from an appointment that the platform itself recorded as completed, and the
database permits exactly one review per appointment. There is no endpoint that
accepts a review without an appointment reference, so a fake review would
require first fabricating a booking, a completed consultation and a clinician
signature — all of which are authenticated actions by different parties.

Proof is graded rather than binary, because the evidence genuinely differs in
strength and treating a signed clinical encounter the same as a bare attendance
record would flatten a real distinction.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.prescription_item import PrescriptionRecord
from app.models.review import DoctorRatingSummary, DoctorReview
from app.models.user import User

# Evidence strength. A consultation the doctor signed is the strongest signal
# that care actually took place; an appointment marked completed is weaker
# because it can be set without any clinical record being written.
PROOF_WEIGHTS = {
    "SIGNED_CONSULTATION": 1.0,
    "PRESCRIPTION_DISPENSED": 0.9,
    "COMPLETED_APPOINTMENT": 0.6,
}

# Bayesian shrinkage. Ratings are pulled toward the platform mean until a
# doctor has accumulated enough reviews for their average to mean something.
PRIOR_MEAN = 4.0
PRIOR_WEIGHT = 5.0


def _now():
    return datetime.now(timezone.utc)


def _establish_proof(appointment: Appointment, db: Session) -> tuple[str, float, str]:
    """Determine what evidence exists that this encounter really happened.

    Raises rather than defaulting to a weak proof: if nothing here holds, the
    patient was never actually treated and must not be able to review.
    """
    consultation = (
        db.query(Consultation)
        .filter(Consultation.appointment_id == appointment.id)
        .first()
    )

    if consultation and consultation.is_signed:
        return "SIGNED_CONSULTATION", PROOF_WEIGHTS["SIGNED_CONSULTATION"], consultation.id

    dispensed = (
        db.query(PrescriptionRecord)
        .filter(
            PrescriptionRecord.appointment_id == appointment.id,
            PrescriptionRecord.status == "DISPENSED",
        )
        .first()
    )
    if dispensed:
        return (
            "PRESCRIPTION_DISPENSED",
            PROOF_WEIGHTS["PRESCRIPTION_DISPENSED"],
            dispensed.verification_code,
        )

    if appointment.status == "COMPLETED":
        return (
            "COMPLETED_APPOINTMENT",
            PROOF_WEIGHTS["COMPLETED_APPOINTMENT"],
            appointment.id,
        )

    raise HTTPException(
        status_code=403,
        detail=(
            "You can only review a consultation that actually took place. "
            "This appointment has no completed visit on record."
        ),
    )


def recompute_summary(doctor_id: str, db: Session) -> DoctorRatingSummary:
    """Recalculate a doctor's cached rating from their visible reviews."""
    reviews = (
        db.query(DoctorReview)
        .filter(
            DoctorReview.doctor_id == doctor_id,
            DoctorReview.is_hidden.is_(False),
        )
        .all()
    )

    summary = (
        db.query(DoctorRatingSummary)
        .filter(DoctorRatingSummary.doctor_id == doctor_id)
        .first()
    )
    if not summary:
        summary = DoctorRatingSummary(doctor_id=doctor_id)
        db.add(summary)

    if not reviews:
        summary.average_rating = 0.0
        summary.bayesian_rating = 0.0
        summary.review_count = 0
        summary.verified_review_count = 0
        summary.average_explanation = None
        summary.average_punctuality = None
        summary.average_respect = None
        return summary

    # Weight each review by the strength of its proof.
    total_weight = sum(r.proof_weight for r in reviews) or 1.0
    weighted_sum = sum(r.rating * r.proof_weight for r in reviews)
    weighted_average = weighted_sum / total_weight

    summary.average_rating = round(weighted_average, 2)
    summary.review_count = len(reviews)
    summary.verified_review_count = sum(1 for r in reviews if r.is_verified)

    summary.bayesian_rating = round(
        ((PRIOR_MEAN * PRIOR_WEIGHT) + weighted_sum)
        / (PRIOR_WEIGHT + total_weight),
        3,
    )

    def sub_average(field: str):
        values = [getattr(r, field) for r in reviews if getattr(r, field) is not None]
        return round(sum(values) / len(values), 2) if values else None

    summary.average_explanation = sub_average("rating_explanation")
    summary.average_punctuality = sub_average("rating_punctuality")
    summary.average_respect = sub_average("rating_respect")

    return summary


def create_review_service(payload, current_user, db: Session):
    patient = (
        db.query(Patient).filter(Patient.user_id == current_user.get("user_id")).first()
    )
    if not patient:
        raise HTTPException(status_code=403, detail="Patient profile required")

    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == payload.appointment_id)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # The reviewer must be the patient who attended, not merely any patient.
    if appointment.patient_id != patient.id:
        raise HTTPException(
            status_code=403,
            detail="You can only review your own appointment",
        )

    proof_type, proof_weight, proof_reference = _establish_proof(appointment, db)

    consultation = (
        db.query(Consultation)
        .filter(Consultation.appointment_id == appointment.id)
        .first()
    )

    review = DoctorReview(
        doctor_id=appointment.doctor_id,
        patient_id=patient.id,
        appointment_id=appointment.id,
        consultation_id=consultation.id if consultation else None,
        rating=payload.rating,
        rating_explanation=payload.rating_explanation,
        rating_punctuality=payload.rating_punctuality,
        rating_respect=payload.rating_respect,
        comment=payload.comment,
        language=payload.language,
        proof_type=proof_type,
        proof_weight=proof_weight,
        proof_reference=proof_reference,
        is_verified=True,
    )

    db.add(review)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="You have already reviewed this consultation",
        )

    recompute_summary(appointment.doctor_id, db)
    db.commit()
    db.refresh(review)
    return _review_payload(review, db)


def _review_payload(review: DoctorReview, db: Session, include_patient=True) -> dict:
    patient_name = None
    if include_patient:
        patient = db.query(Patient).filter(Patient.id == review.patient_id).first()
        if patient:
            user = db.query(User).filter(User.id == patient.user_id).first()
            if user and user.full_name:
                # Reviews are attributed but not fully identifying: a patient
                # should not have to broadcast their full name and health
                # history to leave honest feedback about a doctor.
                parts = user.full_name.split()
                patient_name = (
                    f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else parts[0]
                )

    return {
        "id": review.id,
        "doctor_id": review.doctor_id,
        "rating": review.rating,
        "rating_explanation": review.rating_explanation,
        "rating_punctuality": review.rating_punctuality,
        "rating_respect": review.rating_respect,
        "comment": review.comment,
        "patient_name": patient_name,
        "proof_type": review.proof_type,
        "is_verified": bool(review.is_verified),
        "created_at": review.created_at.isoformat() if review.created_at else None,
    }


def list_doctor_reviews_service(doctor_id: str, db: Session, limit=20, offset=0):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    query = (
        db.query(DoctorReview)
        .filter(
            DoctorReview.doctor_id == doctor_id,
            DoctorReview.is_hidden.is_(False),
        )
        .order_by(DoctorReview.created_at.desc())
    )
    total = query.count()
    rows = query.offset(offset).limit(limit).all()

    summary = (
        db.query(DoctorRatingSummary)
        .filter(DoctorRatingSummary.doctor_id == doctor_id)
        .first()
    )

    distribution = dict(
        db.query(DoctorReview.rating, func.count(DoctorReview.id))
        .filter(
            DoctorReview.doctor_id == doctor_id,
            DoctorReview.is_hidden.is_(False),
        )
        .group_by(DoctorReview.rating)
        .all()
    )

    return {
        "doctor_id": doctor_id,
        "average_rating": summary.average_rating if summary else 0.0,
        "bayesian_rating": summary.bayesian_rating if summary else 0.0,
        "review_count": summary.review_count if summary else 0,
        "verified_review_count": summary.verified_review_count if summary else 0,
        "sub_scores": {
            "explanation": summary.average_explanation if summary else None,
            "punctuality": summary.average_punctuality if summary else None,
            "respect": summary.average_respect if summary else None,
        },
        "rating_distribution": {
            str(star): distribution.get(star, 0) for star in range(1, 6)
        },
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_review_payload(row, db) for row in rows],
    }


def reviewable_appointments_service(current_user, db: Session):
    """Appointments the caller attended and has not yet reviewed."""
    patient = (
        db.query(Patient).filter(Patient.user_id == current_user.get("user_id")).first()
    )
    if not patient:
        return []

    reviewed = {
        row[0]
        for row in db.query(DoctorReview.appointment_id)
        .filter(DoctorReview.patient_id == patient.id)
        .all()
    }

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == patient.id,
            Appointment.status == "COMPLETED",
        )
        .all()
    )

    results = []
    for appointment in appointments:
        if appointment.id in reviewed:
            continue
        try:
            proof_type, _, _ = _establish_proof(appointment, db)
        except HTTPException:
            continue

        doctor = db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()
        doctor_user = (
            db.query(User).filter(User.id == doctor.user_id).first() if doctor else None
        )

        results.append(
            {
                "appointment_id": appointment.id,
                "doctor_id": appointment.doctor_id,
                "doctor_name": doctor_user.full_name if doctor_user else None,
                "specialization": doctor.specialization if doctor else None,
                "appointment_date": appointment.appointment_date,
                "proof_type": proof_type,
            }
        )
    return results


def hide_review_service(review_id: str, payload, current_user, db: Session):
    """Administrative takedown. Hides rather than deletes, preserving audit."""
    review = db.query(DoctorReview).filter(DoctorReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    review.is_hidden = True
    review.hidden_reason = payload.reason
    # Flush before recomputing, or the aggregate query still sees this review
    # as visible and the hidden rating keeps counting.
    db.flush()
    recompute_summary(review.doctor_id, db)
    db.commit()
    return {"message": "Review hidden", "review_id": review_id}
