from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query

from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import get_current_user

from app.modules.recommendations.service import recommend_doctors_service

router = APIRouter()


@router.get("/recommendations/doctors")
def recommend_doctors(
    specialty: str | None = None,
    condition: str | None = None,
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    district: str | None = None,
    urgent: bool = False,
    max_fee: float | None = Query(default=None, ge=0),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Rank doctors for a condition near a location, by verified quality.

    Weighting shifts with urgency: proximity and availability dominate for an
    emergency, reputation for a routine complaint.
    """
    return recommend_doctors_service(
        db,
        specialty=specialty,
        condition=condition,
        latitude=latitude,
        longitude=longitude,
        district=district,
        urgent=urgent,
        max_fee=max_fee,
        limit=limit,
    )
