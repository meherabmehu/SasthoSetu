from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query

from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import get_current_user, require_admin

from app.schemas.review import ReviewCreate, ReviewHide

from app.modules.reviews.service import (
    create_review_service,
    hide_review_service,
    list_doctor_reviews_service,
    reviewable_appointments_service,
)

router = APIRouter()


@router.post("/reviews")
def create_review(
    payload: ReviewCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit a review for a consultation that actually took place.

    Rejected unless the platform holds evidence of the encounter: a signed
    consultation, a dispensed prescription, or a completed appointment.
    """
    return create_review_service(payload, current_user, db)


@router.get("/reviews/pending")
def reviewable_appointments(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Visits the caller attended and has not yet reviewed."""
    return reviewable_appointments_service(current_user, db)


@router.get("/doctors/{doctor_id}/reviews")
def doctor_reviews(
    doctor_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return list_doctor_reviews_service(doctor_id, db, limit=limit, offset=offset)


@router.post("/reviews/{review_id}/hide")
def hide_review(
    review_id: str,
    payload: ReviewHide,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)
    return hide_review_service(review_id, payload, current_user, db)
