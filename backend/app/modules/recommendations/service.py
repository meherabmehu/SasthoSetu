# -*- coding: utf-8 -*-
"""Location-aware doctor recommendation for an identified condition.

Ranking combines four signals that pull in different directions, so the
weighting is explicit rather than emergent:

* **specialty match** — does this doctor treat the condition at all
* **proximity** — a brilliant doctor four hours away is not the answer to
  chest pain today
* **verified rating** — Bayesian-shrunk so a single review cannot outrank a
  long track record
* **availability** — a doctor with no free slot this week cannot help now

Weighting shifts with urgency. For an emergency, distance and availability
dominate because time is the binding constraint; for a routine complaint,
reputation matters more than saving twenty minutes of travel.
"""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Optional

from sqlalchemy.orm import Session

from app.models.doctor import Doctor
from app.models.doctor_availability import DoctorAvailability
from app.models.hospital import Hospital, Ward
from app.models.review import DoctorRatingSummary
from app.models.user import User

# Lexicon and profile vocabularies differ; this keeps matching from silently
# returning nothing.
SPECIALTY_ALIASES = {
    "General Medicine": ["General Medicine", "General Physician", "Internal Medicine"],
    "General Physician": ["General Physician", "General Medicine", "Internal Medicine"],
    "Internal Medicine": ["Internal Medicine", "General Medicine", "General Physician"],
    "Emergency Medicine": ["Emergency Medicine", "Emergency", "General Medicine"],
    "Emergency": ["Emergency", "Emergency Medicine", "General Medicine"],
    "Cardiology": ["Cardiology"],
    "Pulmonology": ["Pulmonology", "Respiratory Medicine"],
    "Neurology": ["Neurology"],
    "Gastroenterology": ["Gastroenterology"],
    "Dermatology": ["Dermatology"],
    "ENT": ["ENT", "Otolaryngology"],
    "Orthopedics": ["Orthopedics", "Orthopaedics"],
    "Paediatrics": ["Paediatrics", "Pediatrics"],
    "Gynaecology & Obstetrics": ["Gynaecology & Obstetrics", "Gynaecology"],
    "Psychiatry": ["Psychiatry"],
    "Endocrinology": ["Endocrinology"],
    "Nephrology": ["Nephrology"],
    "Urology": ["Urology"],
    "Ophthalmology": ["Ophthalmology"],
    "Dentistry": ["Dentistry"],
}

# (specialty, distance, rating, availability)
URGENT_WEIGHTS = (0.30, 0.35, 0.15, 0.20)
ROUTINE_WEIGHTS = (0.35, 0.15, 0.35, 0.15)

# Beyond this a facility is treated as effectively out of reach for same-day
# care, and the distance score bottoms out.
MAX_USEFUL_KM = 40.0


def haversine_km(lat1, lon1, lat2, lon2) -> Optional[float]:
    if None in (lat1, lon1, lat2, lon2):
        return None
    radius = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    return round(2 * radius * asin(sqrt(a)), 2)


def _specialty_score(doctor_specialty: str, target: Optional[str]) -> float:
    if not target:
        return 0.5
    accepted = SPECIALTY_ALIASES.get(target, [target])
    if doctor_specialty == target:
        return 1.0
    if doctor_specialty in accepted:
        return 0.8
    if doctor_specialty in ("General Medicine", "General Physician", "Internal Medicine"):
        # A generalist can always triage onward, so never score them at zero.
        return 0.35
    return 0.1


def _distance_score(distance_km: Optional[float]) -> float:
    if distance_km is None:
        return 0.5
    if distance_km >= MAX_USEFUL_KM:
        return 0.05
    return max(0.05, 1.0 - (distance_km / MAX_USEFUL_KM))


def _rating_score(summary: Optional[DoctorRatingSummary]) -> float:
    if not summary or summary.review_count == 0:
        # An unreviewed doctor is unknown, not bad. Scoring them at zero would
        # make it impossible for any new doctor to ever receive a patient.
        return 0.55
    return min(1.0, summary.bayesian_rating / 5.0)


def recommend_doctors_service(
    db: Session,
    specialty: Optional[str] = None,
    condition: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    district: Optional[str] = None,
    urgent: bool = False,
    max_fee: Optional[float] = None,
    limit: int = 10,
):
    """Rank doctors for a condition, near a location, by verified quality."""
    query = db.query(Doctor).filter(Doctor.verification_status.is_(True))
    if max_fee is not None:
        query = query.filter(Doctor.consultation_fee <= max_fee)

    doctors = query.all()
    if not doctors:
        return {"specialty": specialty, "condition": condition, "results": []}

    # Resolve hospital coordinates once. Doctor profiles carry a hospital name
    # rather than a foreign key, so this maps names to known facilities.
    hospitals = db.query(Hospital).filter(Hospital.is_active.is_(True)).all()
    by_name = {h.name.strip().lower(): h for h in hospitals}

    user_ids = [d.user_id for d in doctors]
    names = {
        u.id: u.full_name
        for u in db.query(User).filter(User.id.in_(user_ids)).all()
    }

    summaries = {
        s.doctor_id: s
        for s in db.query(DoctorRatingSummary)
        .filter(DoctorRatingSummary.doctor_id.in_([d.id for d in doctors]))
        .all()
    }

    weights = URGENT_WEIGHTS if urgent else ROUTINE_WEIGHTS
    w_spec, w_dist, w_rate, w_avail = weights

    results = []
    for doctor in doctors:
        hospital = by_name.get((doctor.hospital_name or "").strip().lower())

        if district and hospital and hospital.district.lower() != district.lower():
            continue

        distance_km = None
        if hospital:
            distance_km = haversine_km(
                latitude, longitude, hospital.latitude, hospital.longitude
            )

        next_slot = (
            db.query(DoctorAvailability)
            .filter(
                DoctorAvailability.doctor_id == doctor.id,
                DoctorAvailability.is_booked.is_(False),
            )
            .order_by(
                DoctorAvailability.available_date.asc(),
                DoctorAvailability.start_time.asc(),
            )
            .first()
        )

        summary = summaries.get(doctor.id)

        specialty_score = _specialty_score(doctor.specialization, specialty)
        distance_score = _distance_score(distance_km)
        rating_score = _rating_score(summary)
        availability_score = 1.0 if next_slot else 0.15

        total = (
            w_spec * specialty_score
            + w_dist * distance_score
            + w_rate * rating_score
            + w_avail * availability_score
        )

        emergency_beds = 0
        if hospital and urgent:
            emergency_beds = sum(
                max(0, ward.total_beds - ward.occupied_beds)
                for ward in db.query(Ward)
                .filter(Ward.hospital_id == hospital.id)
                .all()
                if ward.ward_type in ("emergency", "icu")
            )

        results.append(
            {
                "doctor_id": doctor.id,
                "name": names.get(doctor.user_id),
                "specialization": doctor.specialization,
                "experience_years": doctor.experience_years,
                "consultation_fee": doctor.consultation_fee,
                "hospital_name": doctor.hospital_name,
                "hospital_id": hospital.id if hospital else None,
                "district": hospital.district if hospital else None,
                "area": hospital.area if hospital else None,
                "hospital_phone": hospital.phone if hospital else None,
                "has_emergency": bool(hospital.has_emergency) if hospital else None,
                "available_emergency_beds": emergency_beds if urgent else None,
                "distance_km": distance_km,
                "rating": summary.average_rating if summary else None,
                "bayesian_rating": summary.bayesian_rating if summary else None,
                "review_count": summary.review_count if summary else 0,
                "verified_review_count": (
                    summary.verified_review_count if summary else 0
                ),
                "next_available_date": next_slot.available_date if next_slot else None,
                "next_available_time": next_slot.start_time if next_slot else None,
                "has_availability": next_slot is not None,
                "match_score": round(total, 4),
                # Exposed so the interface can explain the ranking instead of
                # presenting an unexplained order.
                "score_breakdown": {
                    "specialty": round(specialty_score, 3),
                    "distance": round(distance_score, 3),
                    "rating": round(rating_score, 3),
                    "availability": round(availability_score, 3),
                },
            }
        )

    results.sort(key=lambda item: -item["match_score"])

    return {
        "specialty": specialty,
        "condition": condition,
        "urgent": urgent,
        "ranked_by": (
            "proximity and availability (urgent)"
            if urgent
            else "specialty match and verified rating"
        ),
        "results": results[:limit],
    }
