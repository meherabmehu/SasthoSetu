from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.ai.drug_safety import check_interactions
from app.ai.triage_service import triage as run_ml_triage
from app.ai import surge_service
from app.ai import surveillance_service
from app.models.ai_feedback import AIFeedback


def drug_check_service(drugs: list[str]):
    try:
        return check_interactions(drugs)
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Drug knowledge base missing - run ml/generate_drug_kb.py"
        )


def ml_triage_service(notes: str, age: int | None = None):
    try:
        return run_ml_triage(notes, age=age)
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Triage model artifact missing - run ml/train_triage_model.py"
        )


def surge_forecast_service(hospital_code: str):
    try:
        return surge_service.forecast(hospital_code.upper())
    except FileNotFoundError:
        # Never surface the filesystem path: it discloses server layout and
        # tells the caller nothing they can act on.
        raise HTTPException(
            status_code=503,
            detail="Surge model artifact missing - run ml/train_surge_model.py"
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


def surveillance_service_query(district: str | None, disease: str | None,
                                weeks: int):
    try:
        return surveillance_service.surveillance(
            district=district, disease=disease, weeks=min(weeks, 60))
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Surveillance dataset missing - run ml/generate_surveillance.py"
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


def record_feedback_service(payload, current_user: dict, db: Session):
    row = AIFeedback(
        user_id=current_user.get("user_id"),
        feature=payload.feature,
        input_text=payload.input_text,
        correct=payload.correct,
        corrected_level=payload.corrected_level,
        comment=payload.comment,
    )
    db.add(row)
    db.commit()
    return {
        "id": row.id,
        "status": "recorded",
        "note": "Feedback is folded into retraining via "
                "ml/retrain_from_feedback.py",
    }
