from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.ai.triage_service import triage as ml_triage
from app.models.doctor import Doctor
from app.models.doctor_availability import DoctorAvailability
from app.models.patient import Patient
from app.models.triage_session import TriageSession
from app.modules.symptom_checker.service import triage_symptoms
from app.schemas.triage import TriageRequest

LEVEL_TO_NAME = {
    1: "SELF_CARE",
    2: "TELECONSULT",
    3: "GP_VISIT",
    4: "SPECIALIST",
    5: "EMERGENCY",
}

# Lexicon specialties are clinical labels; doctor profiles use the registration
# specialisation wording. This maps between them so matching does not silently
# return nothing.
SPECIALTY_ALIASES = {
    "General Medicine": ["General Medicine", "General Physician", "Internal Medicine"],
    "General Physician": ["General Physician", "General Medicine", "Internal Medicine"],
    "Internal Medicine": ["Internal Medicine", "General Medicine", "General Physician"],
    "Emergency": ["Emergency", "Emergency Medicine", "General Medicine"],
    "Emergency Medicine": ["Emergency Medicine", "Emergency", "General Medicine"],
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


def _resolve_patient(user, db: Session):
    if not user:
        return None, None
    patient = (
        db.query(Patient).filter(Patient.user_id == user.get("user_id")).first()
    )
    return (patient.id if patient else None), user.get("user_id")


def create_triage_session_service(
    payload: TriageRequest,
    current_user,
    db: Session,
    engine: str = "rules",
    latitude: float | None = None,
    longitude: float | None = None,
):
    """Run triage and persist the assessment."""
    if engine == "ml":
        try:
            raw = ml_triage(payload.symptoms, age=payload.age_years)
        except FileNotFoundError:
            raise HTTPException(
                status_code=503,
                detail="Triage model artifact missing - run ml/train_triage_model.py",
            )
        severity = raw["severity_level"]
        result = {
            "triage_level": LEVEL_TO_NAME[severity],
            "severity_level": severity,
            "possible_condition": raw["recommended_pathway"]["en"],
            "possible_condition_bn": raw["recommended_pathway"]["bn"],
            "recommended_specialty": (raw["matched_specialties"] or ["General Physician"])[0],
            "confidence": round(raw["confidence_score"] * 100),
            "matched_symptoms": raw["entities"]["symptoms"],
            "safety_flags": [f["flag"] for f in raw["safety_flags"]],
            "advice": raw["recommended_pathway"]["en"],
            "advice_bn": raw["recommended_pathway"]["bn"],
            "disclaimer": raw["disclaimer"]["en"],
            "disclaimer_bn": raw["disclaimer"]["bn"],
            "model_version": raw["model_version"],
        }
    else:
        response = triage_symptoms(payload)
        result = response.model_dump()
        result["triage_level"] = response.triage_level.value
        result["severity_level"] = {
            v: k for k, v in LEVEL_TO_NAME.items()
        }[response.triage_level.value]
        result["model_version"] = "rules-v1.1"

    patient_id, user_id = _resolve_patient(current_user, db)

    session = TriageSession(
        patient_id=patient_id,
        user_id=user_id,
        input_text=payload.symptoms,
        language=payload.language,
        age_years=payload.age_years,
        temperature_c=payload.temperature_c,
        engine=engine,
        model_version=result.get("model_version"),
        triage_level=result["triage_level"],
        severity_level=result["severity_level"],
        possible_condition=result.get("possible_condition"),
        recommended_specialty=result.get("recommended_specialty"),
        confidence=float(result.get("confidence") or 0),
        matched_symptoms=result.get("matched_symptoms"),
        safety_flags=result.get("safety_flags"),
        latitude=latitude,
        longitude=longitude,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    result["triage_session_id"] = session.id
    result["engine"] = engine
    return result


def get_triage_session_service(session_id: str, current_user, db: Session):
    session = (
        db.query(TriageSession).filter(TriageSession.id == session_id).first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Triage session not found")

    role = current_user.get("role")
    if role not in ("ADMIN", "DOCTOR") and session.user_id != current_user.get(
        "user_id"
    ):
        raise HTTPException(
            status_code=403, detail="You cannot view this triage session"
        )

    return _session_payload(session)


def _session_payload(session: TriageSession) -> dict:
    return {
        "id": session.id,
        "input_text": session.input_text,
        "language": session.language,
        "age_years": session.age_years,
        "engine": session.engine,
        "model_version": session.model_version,
        "triage_level": session.triage_level,
        "severity_level": session.severity_level,
        "possible_condition": session.possible_condition,
        "recommended_specialty": session.recommended_specialty,
        "confidence": session.confidence,
        "matched_symptoms": session.matched_symptoms or [],
        "safety_flags": session.safety_flags or [],
        "clinician_level": session.clinician_level,
        "was_overridden": bool(session.was_overridden),
        "review_note": session.review_note,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


def list_my_triage_sessions_service(current_user, db: Session, limit=20, offset=0):
    query = (
        db.query(TriageSession)
        .filter(TriageSession.user_id == current_user.get("user_id"))
        .order_by(TriageSession.created_at.desc())
    )
    total = query.count()
    rows = query.offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_session_payload(row) for row in rows],
    }


def review_triage_session_service(session_id: str, payload, current_user, db: Session):
    """Record a clinician's agreement or override on a triage assessment."""
    session = (
        db.query(TriageSession).filter(TriageSession.id == session_id).first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Triage session not found")

    doctor = (
        db.query(Doctor).filter(Doctor.user_id == current_user.get("user_id")).first()
    )
    if not doctor:
        raise HTTPException(
            status_code=403, detail="Only a registered doctor can review triage"
        )

    session.reviewed_by = doctor.id
    session.clinician_level = payload.clinician_level
    session.review_note = payload.note
    session.was_overridden = payload.clinician_level != session.severity_level
    db.commit()
    db.refresh(session)
    return _session_payload(session)


def match_doctors_service(
    db: Session,
    specialty: str | None = None,
    triage_session_id: str | None = None,
    language: str | None = None,
    max_fee: float | None = None,
    limit: int = 10,
):
    """Rank verified doctors who can see this patient, soonest first."""
    resolved_specialty = specialty

    if triage_session_id:
        session = (
            db.query(TriageSession)
            .filter(TriageSession.id == triage_session_id)
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Triage session not found")
        resolved_specialty = resolved_specialty or session.recommended_specialty

    query = db.query(Doctor).filter(Doctor.verification_status.is_(True))

    if resolved_specialty:
        candidates = SPECIALTY_ALIASES.get(
            resolved_specialty, [resolved_specialty]
        )
        query = query.filter(Doctor.specialization.in_(candidates))

    if max_fee is not None:
        query = query.filter(Doctor.consultation_fee <= max_fee)

    doctors = query.all()

    # Fall back to general medicine rather than returning an empty list: a
    # patient who has just been told to see a doctor must always be offered
    # one. Any explicit filter the patient set is still respected.
    if not doctors and resolved_specialty:
        fallback = db.query(Doctor).filter(
            Doctor.verification_status.is_(True),
            Doctor.specialization.in_(
                ["General Medicine", "General Physician", "Internal Medicine"]
            ),
        )
        if max_fee is not None:
            fallback = fallback.filter(Doctor.consultation_fee <= max_fee)
        doctors = fallback.all()

    results = []
    for doctor in doctors:
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

        results.append(
            {
                "doctor_id": doctor.id,
                "name": None,
                "specialization": doctor.specialization,
                "experience_years": doctor.experience_years,
                "consultation_fee": doctor.consultation_fee,
                "hospital_name": doctor.hospital_name,
                "bio": doctor.bio,
                "next_available_date": next_slot.available_date if next_slot else None,
                "next_available_time": next_slot.start_time if next_slot else None,
                "has_availability": next_slot is not None,
                "matched_specialty": resolved_specialty,
            }
        )

    # Attach display names in one query rather than per doctor.
    from app.models.user import User

    user_ids = {d.user_id: None for d in doctors}
    if user_ids:
        for user in db.query(User).filter(User.id.in_(list(user_ids))).all():
            user_ids[user.id] = user.full_name
    for doctor, row in zip(doctors, results, strict=True):
        row["name"] = user_ids.get(doctor.user_id)

    results.sort(
        key=lambda r: (
            0 if r["has_availability"] else 1,
            r["next_available_date"] or "9999-12-31",
            r["next_available_time"] or "23:59",
            -(r["experience_years"] or 0),
        )
    )
    return results[:limit]
