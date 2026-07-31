import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.ai.drug_safety import check_interactions, normalize_drug
from app.core.config import settings
from app.models.appointment import Appointment
from app.models.consultation import Consultation, ConsultationMessage
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.prescription_item import PrescriptionLine, PrescriptionRecord
from app.models.user import User
from app.modules.notifications.service import create_notification

# Codes are read aloud and typed at pharmacy counters, so the alphabet omits
# characters that are easily confused (0/O, 1/I).
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 10


def _now():
    return datetime.now(timezone.utc)


def _generate_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def _stamp(value) -> str:
    """Timestamp form used inside the signature.

    Normalised to naive UTC seconds because some database drivers (SQLite in
    particular) return the value without its timezone, which would otherwise
    make a genuine prescription fail its own signature check on read-back.
    """
    if value is None:
        return ""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.replace(microsecond=0).isoformat()


def _canonical_payload(record: PrescriptionRecord, lines: list[dict]) -> str:
    """Stable representation of the clinical content that the signature covers."""
    return json.dumps(
        {
            "code": record.verification_code,
            "doctor_id": record.doctor_id,
            "patient_id": record.patient_id,
            "diagnosis": record.diagnosis or "",
            "issued_at": _stamp(record.issued_at),
            "valid_until": _stamp(record.valid_until),
            "items": lines,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sign_payload(payload: str) -> str:
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _require_doctor(current_user, db: Session) -> Doctor:
    doctor = (
        db.query(Doctor).filter(Doctor.user_id == current_user.get("user_id")).first()
    )
    if not doctor:
        raise HTTPException(status_code=403, detail="Doctor profile required")
    if not doctor.verification_status:
        raise HTTPException(
            status_code=403, detail="Doctor is not verified by BMDC"
        )
    return doctor


def _consultation_payload(consultation: Consultation) -> dict:
    return {
        "id": consultation.id,
        "appointment_id": consultation.appointment_id,
        "doctor_id": consultation.doctor_id,
        "patient_id": consultation.patient_id,
        "triage_session_id": consultation.triage_session_id,
        "status": consultation.status,
        "chief_complaint": consultation.chief_complaint,
        "examination_notes": consultation.examination_notes,
        "diagnosis": consultation.diagnosis,
        "advice": consultation.advice,
        "follow_up_date": consultation.follow_up_date,
        "investigations": consultation.investigations or [],
        "is_signed": bool(consultation.is_signed),
        "started_at": (
            consultation.started_at.isoformat() if consultation.started_at else None
        ),
        "closed_at": (
            consultation.closed_at.isoformat() if consultation.closed_at else None
        ),
    }


def start_consultation_service(payload, current_user, db: Session):
    doctor = _require_doctor(current_user, db)

    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == payload.appointment_id)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.doctor_id != doctor.id:
        raise HTTPException(
            status_code=403, detail="This appointment belongs to another doctor"
        )
    if appointment.status in ("CANCELLED", "REJECTED"):
        raise HTTPException(
            status_code=400, detail="Cannot consult on a cancelled appointment"
        )

    existing = (
        db.query(Consultation)
        .filter(Consultation.appointment_id == appointment.id)
        .first()
    )
    if existing:
        return _consultation_payload(existing)

    consultation = Consultation(
        appointment_id=appointment.id,
        doctor_id=doctor.id,
        patient_id=appointment.patient_id,
        triage_session_id=payload.triage_session_id,
        chief_complaint=payload.chief_complaint or appointment.reason,
        status="OPEN",
    )
    appointment.status = "IN_PROGRESS"
    db.add(consultation)
    db.commit()
    db.refresh(consultation)
    return _consultation_payload(consultation)


def _load_consultation(consultation_id: str, db: Session) -> Consultation:
    consultation = (
        db.query(Consultation).filter(Consultation.id == consultation_id).first()
    )
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return consultation


def _assert_participant(consultation: Consultation, current_user, db: Session):
    role = current_user.get("role")
    user_id = current_user.get("user_id")

    if role == "ADMIN":
        return "ADMIN"

    doctor = db.query(Doctor).filter(Doctor.user_id == user_id).first()
    if doctor and doctor.id == consultation.doctor_id:
        return "DOCTOR"

    patient = db.query(Patient).filter(Patient.user_id == user_id).first()
    if patient and patient.id == consultation.patient_id:
        return "PATIENT"

    raise HTTPException(
        status_code=403, detail="You are not a participant in this consultation"
    )


def get_consultation_service(consultation_id: str, current_user, db: Session):
    consultation = _load_consultation(consultation_id, db)
    _assert_participant(consultation, current_user, db)
    return _consultation_payload(consultation)


def update_consultation_service(consultation_id: str, payload, current_user, db: Session):
    consultation = _load_consultation(consultation_id, db)
    doctor = _require_doctor(current_user, db)

    if consultation.doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="Not your consultation")
    if consultation.is_signed:
        raise HTTPException(
            status_code=409,
            detail="Consultation is signed and can no longer be edited",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(consultation, field, value)

    db.commit()
    db.refresh(consultation)
    return _consultation_payload(consultation)


def close_consultation_service(consultation_id: str, current_user, db: Session):
    consultation = _load_consultation(consultation_id, db)
    doctor = _require_doctor(current_user, db)

    if consultation.doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="Not your consultation")
    if consultation.is_signed:
        return _consultation_payload(consultation)

    if not consultation.diagnosis:
        raise HTTPException(
            status_code=400,
            detail="A diagnosis is required before closing the consultation",
        )

    consultation.status = "COMPLETED"
    consultation.is_signed = True
    consultation.closed_at = _now()

    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == consultation.appointment_id)
        .first()
    )
    if appointment:
        appointment.status = "COMPLETED"

    patient = (
        db.query(Patient).filter(Patient.id == consultation.patient_id).first()
    )
    if patient:
        create_notification(
            user_id=patient.user_id,
            title="Consultation completed",
            message="Your consultation notes and prescription are now available.",
            db=db,
        )

    db.commit()
    db.refresh(consultation)
    return _consultation_payload(consultation)


def post_message_service(consultation_id: str, payload, current_user, db: Session):
    consultation = _load_consultation(consultation_id, db)
    role = _assert_participant(consultation, current_user, db)

    if consultation.status == "COMPLETED":
        raise HTTPException(
            status_code=409, detail="Consultation is closed to new messages"
        )

    message = ConsultationMessage(
        consultation_id=consultation.id,
        sender_user_id=current_user.get("user_id"),
        sender_role=role,
        body=payload.body,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return {
        "id": message.id,
        "sender_role": message.sender_role,
        "body": message.body,
        "sent_at": message.sent_at.isoformat() if message.sent_at else None,
    }


def list_messages_service(consultation_id: str, current_user, db: Session):
    consultation = _load_consultation(consultation_id, db)
    _assert_participant(consultation, current_user, db)

    rows = (
        db.query(ConsultationMessage)
        .filter(ConsultationMessage.consultation_id == consultation.id)
        .order_by(ConsultationMessage.sequence.asc())
        .all()
    )
    return [
        {
            "id": row.id,
            "sender_role": row.sender_role,
            "body": row.body,
            "sent_at": row.sent_at.isoformat() if row.sent_at else None,
        }
        for row in rows
    ]


def issue_prescription_service(payload, current_user, db: Session):
    doctor = _require_doctor(current_user, db)

    consultation = None
    if payload.consultation_id:
        consultation = _load_consultation(payload.consultation_id, db)
        if consultation.doctor_id != doctor.id:
            raise HTTPException(status_code=403, detail="Not your consultation")
        patient_id = consultation.patient_id
        appointment_id = consultation.appointment_id
    elif payload.appointment_id:
        appointment = (
            db.query(Appointment)
            .filter(Appointment.id == payload.appointment_id)
            .first()
        )
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")
        if appointment.doctor_id != doctor.id:
            raise HTTPException(status_code=403, detail="Not your appointment")
        patient_id = appointment.patient_id
        appointment_id = appointment.id
    else:
        raise HTTPException(
            status_code=400,
            detail="Either consultation_id or appointment_id is required",
        )

    # Screen the whole prescription before it is signed, not after.
    report = check_interactions([item.medicine_name for item in payload.items])

    issued_at = _now()
    record = PrescriptionRecord(
        consultation_id=payload.consultation_id,
        appointment_id=appointment_id,
        doctor_id=doctor.id,
        patient_id=patient_id,
        diagnosis=payload.diagnosis
        or (consultation.diagnosis if consultation else None),
        advice=payload.advice,
        verification_code=_generate_code(),
        signature="",
        issued_at=issued_at,
        valid_until=issued_at + timedelta(days=payload.valid_days),
        interaction_report=report,
        status="ACTIVE",
    )

    line_payloads = []
    for item in payload.items:
        line_payloads.append(
            {
                "medicine_name": item.medicine_name,
                "generic_name": normalize_drug(item.medicine_name),
                "strength": item.strength or "",
                "dosage_form": item.dosage_form,
                "frequency": item.frequency,
                "duration": item.duration,
                "route": item.route,
                "instructions": item.instructions or "",
            }
        )

    record.signature = sign_payload(_canonical_payload(record, line_payloads))
    db.add(record)
    db.flush()

    for line in line_payloads:
        db.add(PrescriptionLine(prescription_id=record.id, **line))

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient:
        create_notification(
            user_id=patient.user_id,
            title="Prescription issued",
            message=(
                f"Your prescription {record.verification_code} is ready. "
                "Show the code at any verified pharmacy."
            ),
            db=db,
        )

    db.commit()
    db.refresh(record)
    return _prescription_payload(record, db, include_signature=True)


def _prescription_payload(record: PrescriptionRecord, db: Session, include_signature=False):
    lines = (
        db.query(PrescriptionLine)
        .filter(PrescriptionLine.prescription_id == record.id)
        .order_by(PrescriptionLine.sequence.asc())
        .all()
    )

    doctor = db.query(Doctor).filter(Doctor.id == record.doctor_id).first()
    doctor_user = (
        db.query(User).filter(User.id == doctor.user_id).first() if doctor else None
    )

    payload = {
        "id": record.id,
        "verification_code": record.verification_code,
        "status": record.status,
        "diagnosis": record.diagnosis,
        "advice": record.advice,
        "issued_at": record.issued_at.isoformat() if record.issued_at else None,
        "valid_until": record.valid_until.isoformat() if record.valid_until else None,
        "doctor": {
            "id": record.doctor_id,
            "name": doctor_user.full_name if doctor_user else None,
            "bmdc_number": doctor.bmdc_number if doctor else None,
            "specialization": doctor.specialization if doctor else None,
        },
        "patient_id": record.patient_id,
        "items": [
            {
                "medicine_name": line.medicine_name,
                "generic_name": line.generic_name,
                "strength": line.strength,
                "dosage_form": line.dosage_form,
                "frequency": line.frequency,
                "duration": line.duration,
                "route": line.route,
                "instructions": line.instructions,
            }
            for line in lines
        ],
        "interaction_report": record.interaction_report,
        "dispensed_at": (
            record.dispensed_at.isoformat() if record.dispensed_at else None
        ),
    }
    if include_signature:
        payload["signature"] = record.signature
        payload["qr_payload"] = json.dumps(
            {"code": record.verification_code, "sig": record.signature[:32]},
            separators=(",", ":"),
        )
    return payload


def _validate_record(record: PrescriptionRecord, signature: str | None, db: Session):
    """Return the verification verdict for a prescription."""
    lines = (
        db.query(PrescriptionLine)
        .filter(PrescriptionLine.prescription_id == record.id)
        .order_by(PrescriptionLine.sequence.asc())
        .all()
    )
    line_payloads = [
        {
            "medicine_name": line.medicine_name,
            "generic_name": line.generic_name,
            "strength": line.strength or "",
            "dosage_form": line.dosage_form,
            "frequency": line.frequency,
            "duration": line.duration,
            "route": line.route,
            "instructions": line.instructions or "",
        }
        for line in lines
    ]

    expected = sign_payload(_canonical_payload(record, line_payloads))
    tampered = not hmac.compare_digest(expected, record.signature or "")

    if signature:
        supplied_matches = hmac.compare_digest(
            record.signature[: len(signature)], signature
        )
    else:
        supplied_matches = True

    expired = record.valid_until is not None and _now() > _ensure_aware(
        record.valid_until
    )

    return {
        "is_tampered": tampered,
        "signature_matches": supplied_matches,
        "is_expired": expired,
        "already_dispensed": record.status == "DISPENSED",
        "is_cancelled": bool(record.is_cancelled),
    }


def _ensure_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def verify_prescription_service(payload, db: Session):
    record = (
        db.query(PrescriptionRecord)
        .filter(PrescriptionRecord.verification_code == payload.verification_code.upper())
        .first()
    )
    if not record:
        return {
            "is_valid": False,
            "reason": "No prescription found for this code",
            "reason_bn": "এই কোডে কোনো প্রেসক্রিপশন পাওয়া যায়নি",
        }

    checks = _validate_record(record, payload.signature, db)

    reasons = []
    if checks["is_tampered"] or not checks["signature_matches"]:
        reasons.append(("Prescription signature does not match - possible forgery",
                        "প্রেসক্রিপশনের স্বাক্ষর মেলেনি - জাল হতে পারে"))
    if checks["is_cancelled"]:
        reasons.append(("Prescription was cancelled by the prescriber",
                        "প্রেসক্রিপশনটি বাতিল করা হয়েছে"))
    if checks["is_expired"]:
        reasons.append(("Prescription has expired",
                        "প্রেসক্রিপশনের মেয়াদ শেষ"))
    if checks["already_dispensed"]:
        reasons.append(("Prescription has already been dispensed",
                        "এই প্রেসক্রিপশন আগেই সরবরাহ করা হয়েছে"))

    is_valid = not reasons

    response = {
        "is_valid": is_valid,
        "verification_code": record.verification_code,
        "is_expired": checks["is_expired"],
        "already_dispensed": checks["already_dispensed"],
        "is_cancelled": checks["is_cancelled"],
        "signature_valid": not checks["is_tampered"] and checks["signature_matches"],
        "reason": reasons[0][0] if reasons else "Prescription is valid",
        "reason_bn": reasons[0][1] if reasons else "প্রেসক্রিপশনটি বৈধ",
        "flagged_interactions": (record.interaction_report or {}).get(
            "flagged_interactions", []
        ),
    }

    if is_valid:
        response["prescription"] = _prescription_payload(record, db)
    return response


def dispense_prescription_service(payload, current_user, db: Session):
    record = (
        db.query(PrescriptionRecord)
        .filter(
            PrescriptionRecord.verification_code == payload.verification_code.upper()
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Prescription not found")

    checks = _validate_record(record, payload.signature, db)
    if checks["is_tampered"] or not checks["signature_matches"]:
        raise HTTPException(
            status_code=409, detail="Signature mismatch - refusing to dispense"
        )
    if checks["is_cancelled"]:
        raise HTTPException(status_code=409, detail="Prescription was cancelled")
    if checks["is_expired"]:
        raise HTTPException(status_code=409, detail="Prescription has expired")
    if checks["already_dispensed"]:
        raise HTTPException(
            status_code=409, detail="Prescription has already been dispensed"
        )

    record.status = "DISPENSED"
    record.dispensed_at = _now()
    record.dispensed_by = current_user.get("user_id")

    patient = db.query(Patient).filter(Patient.id == record.patient_id).first()
    if patient:
        create_notification(
            user_id=patient.user_id,
            title="Prescription dispensed",
            message=f"Prescription {record.verification_code} was dispensed.",
            db=db,
        )

    db.commit()
    return {
        "message": "Prescription dispensed",
        "verification_code": record.verification_code,
        "dispensed_at": record.dispensed_at.isoformat(),
    }


def cancel_prescription_service(prescription_id: str, current_user, db: Session):
    record = (
        db.query(PrescriptionRecord)
        .filter(PrescriptionRecord.id == prescription_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Prescription not found")

    doctor = _require_doctor(current_user, db)
    if record.doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="Not your prescription")
    if record.status == "DISPENSED":
        raise HTTPException(
            status_code=409, detail="Cannot cancel a dispensed prescription"
        )

    record.is_cancelled = True
    record.status = "CANCELLED"
    db.commit()
    return {"message": "Prescription cancelled"}


def list_patient_prescriptions_service(patient_user_id: str, current_user, db: Session):
    patient = (
        db.query(Patient).filter(Patient.user_id == patient_user_id).first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    role = current_user.get("role")
    if role not in ("ADMIN", "DOCTOR") and current_user.get("user_id") != patient_user_id:
        raise HTTPException(status_code=403, detail="Not authorised")

    records = (
        db.query(PrescriptionRecord)
        .filter(PrescriptionRecord.patient_id == patient.id)
        .order_by(PrescriptionRecord.issued_at.desc())
        .all()
    )
    return [_prescription_payload(record, db) for record in records]
