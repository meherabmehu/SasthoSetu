from fastapi import APIRouter

from app.schemas.symptom_checker import (
    SymptomRequest
)

from app.modules.symptom_checker.service import (
    analyze_symptoms_service
)

router = APIRouter()


@router.post(
    "/symptom-checker"
)
def analyze_symptoms(
    request: SymptomRequest
):
    return analyze_symptoms_service(
        request.symptoms
    )