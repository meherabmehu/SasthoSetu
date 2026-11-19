from fastapi import APIRouter
from fastapi import Depends

from app.core.security import get_current_user

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
from app.ai.care_pathway_graph import build_care_pathway_graph

router = APIRouter()


@router.post(
    "/triage",
    response_model=TriageResponse,
    summary="Assess symptoms and recommend the safest care pathway",
)
def create_triage(
    request: TriageRequest,
    current_user=Depends(get_current_user),
) -> TriageResponse:
    result = triage_symptoms(request)
    result.care_pathway_graph = build_care_pathway_graph(
        triage_level=result.triage_level.value,
        safety_flags=result.safety_flags,
    )
    return result


@router.post(
    "/symptom-checker",
    response_model=SymptomResponse,
    deprecated=True,
)
def analyze_symptoms(
    request: SymptomRequest,
    current_user=Depends(get_current_user)
):
    return analyze_symptoms_service(
        request.symptoms
    )
