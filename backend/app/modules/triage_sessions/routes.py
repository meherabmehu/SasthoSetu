from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query

from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import get_current_user

from app.schemas.clinical import TriageReview
from app.schemas.triage import TriageRequest

from app.modules.triage_sessions.service import (
    create_triage_session_service,
    get_triage_session_service,
    list_my_triage_sessions_service,
    match_doctors_service,
    review_triage_session_service,
)

router = APIRouter()


@router.post("/triage/sessions")
def create_triage_session(
    payload: TriageRequest,
    engine: str = Query(default="rules", pattern="^(rules|ml)$"),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run triage and store the assessment against the signed-in patient.

    Requires an account so the assessment becomes part of a longitudinal
    record a clinician can review. Someone in an emergency without an account
    is still served by the SMS and IVR channels, which stay open.
    """
    return create_triage_session_service(
        payload,
        current_user,
        db,
        engine=engine,
        latitude=latitude,
        longitude=longitude,
    )


@router.get("/triage/sessions/mine")
def list_my_triage_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_my_triage_sessions_service(current_user, db, limit=limit, offset=offset)


@router.get("/triage/sessions/{session_id}")
def get_triage_session(
    session_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_triage_session_service(session_id, current_user, db)


@router.post("/triage/sessions/{session_id}/review")
def review_triage_session(
    session_id: str,
    payload: TriageReview,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clinician confirms or overrides the assessment, feeding the retrain loop."""
    return review_triage_session_service(session_id, payload, current_user, db)


@router.get("/doctors/match")
def match_doctors(
    specialty: str | None = None,
    triage_session_id: str | None = None,
    language: str | None = None,
    max_fee: float | None = Query(default=None, ge=0),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return match_doctors_service(
        db,
        specialty=specialty,
        triage_session_id=triage_session_id,
        language=language,
        max_fee=max_fee,
        limit=limit,
    )
