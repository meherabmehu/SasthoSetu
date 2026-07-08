from fastapi import APIRouter

from app.schemas.symptom_checker import (
    SymptomRequest,
    SymptomResponse,
)
from app.schemas.triage import (
    TriageRequest,
    TriageResponse,
)

from app.modules.symptom_checker.service import (
    analyze_symptoms_service,
    triage_symptoms,
)

router = APIRouter()


@router.post(
    "/triage",
    response_model=TriageResponse,
    summary="Assess symptoms and recommend the safest care pathway",
)
def create_triage(request: TriageRequest) -> TriageResponse:
    return triage_symptoms(request)


@router.post(
    "/symptom-checker",
    response_model=SymptomResponse,
    deprecated=True,
)
def analyze_symptoms(
    request: SymptomRequest
):
    return analyze_symptoms_service(
        request.symptoms
    )
