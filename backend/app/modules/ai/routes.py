from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import get_current_user

from app.schemas.ai import (
    DrugCheckRequest,
    SurveillanceQuery,
    AIFeedbackCreate,
)
from app.schemas.triage import TriageRequest

from app.modules.ai.service import (
    drug_check_service,
    ml_triage_service,
    surge_forecast_service,
    surveillance_service_query,
    record_feedback_service,
)

router = APIRouter()


@router.post("/ai/drug-check")
def drug_check(payload: DrugCheckRequest):
    return drug_check_service(payload.drugs)


@router.post(
    "/ai/triage-ml",
    summary="Multilingual ML triage (bn/banglish/en) with red-flag safety "
            "override - complements the rule-based /triage endpoint",
)
def triage_ml(request: TriageRequest):
    return ml_triage_service(request.symptoms, age=request.age_years)


@router.get("/hospitals/{hospital_code}/surge-forecast")
def surge_forecast(hospital_code: str):
    return surge_forecast_service(hospital_code)


@router.get("/population/surveillance")
def population_surveillance(query: SurveillanceQuery = Depends()):
    return surveillance_service_query(
        query.district, query.disease, query.weeks)


@router.post("/ai/feedback")
def submit_feedback(
    payload: AIFeedbackCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return record_feedback_service(payload, current_user, db)
