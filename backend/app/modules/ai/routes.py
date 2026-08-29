from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import Form
from fastapi import HTTPException
from fastapi import UploadFile

from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import get_current_user

from app.schemas.ai import (
    DrugCheckRequest,
    SurveillanceQuery,
    AIFeedbackCreate,
)
from app.schemas.triage import TriageRequest

from app.ai.skin_service import (
    SkinModelError,
    assess_skin_image,
    model_available as skin_model_available,
)

from app.ai.xray_service import (
    XrayModelError,
    assess_chest_xray,
    model_available as xray_model_available,
)

from app.modules.ai.service import (
    drug_check_service,
    ml_triage_service,
    surge_forecast_service,
    surveillance_service_query,
    record_feedback_service,
)

router = APIRouter()


@router.post("/ai/drug-check")
def drug_check(
    payload: DrugCheckRequest,
    current_user=Depends(get_current_user),
):
    return drug_check_service(payload.drugs)


@router.post(
    "/ai/triage-ml",
    summary="Multilingual ML triage (bn/banglish/en) with red-flag safety "
            "override - complements the rule-based /triage endpoint",
)
def triage_ml(
    request: TriageRequest,
    current_user=Depends(get_current_user),
):
    return ml_triage_service(request.symptoms, age=request.age_years)


@router.get("/hospitals/{hospital_code}/surge-forecast")
def surge_forecast(
    hospital_code: str,
    current_user=Depends(get_current_user),
):
    return surge_forecast_service(hospital_code)


@router.get("/population/surveillance")
def population_surveillance(
    query: SurveillanceQuery = Depends(),
    current_user=Depends(get_current_user),
):
    return surveillance_service_query(
        query.district, query.disease, query.weeks)


@router.post("/ai/feedback")
def submit_feedback(
    payload: AIFeedbackCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return record_feedback_service(payload, current_user, db)


@router.post(
    "/ai/skin-check",
    summary="Assess a photograph of a skin lesion and decide whether it "
            "needs a dermatologist",
)
async def skin_check(
    image: UploadFile = File(...),
    age_years: int | None = Form(default=None),
    current_user=Depends(get_current_user),
):
    """Read one photograph and return a referral band.

    Deliberately not a diagnosis: the model was trained on dermatoscope images
    and a phone photograph is a harder problem. The response leads with what
    the patient should do and carries the disclaimer in both languages.
    """
    payload = await image.read()

    if not payload:
        raise HTTPException(status_code=400, detail="No image was uploaded")

    try:
        return assess_skin_image(payload, age=age_years)
    except SkinModelError as error:
        # A missing artifact is a setup step the operator has not run, not a
        # fault in the request.
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get(
    "/ai/skin-check/status",
    summary="Whether the skin lesion model is built and servable",
)
def skin_check_status(current_user=Depends(get_current_user)):
    return {"available": skin_model_available()}


@router.post(
    "/ai/xray-check",
    summary="Screen a chest X-ray for signs of pneumonia",
)
async def xray_check(
    image: UploadFile = File(...),
    age_years: int | None = Form(default=None),
    current_user=Depends(get_current_user),
):
    """Screen one chest film.

    A screen, not a report. It cannot rule pneumonia out, and the response
    says so in both languages.
    """
    payload = await image.read()

    if not payload:
        raise HTTPException(status_code=400, detail="No image was uploaded")

    try:
        return assess_chest_xray(payload, age=age_years)
    except XrayModelError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get(
    "/ai/xray-check/status",
    summary="Whether the chest X-ray model is built and servable",
)
def xray_check_status(current_user=Depends(get_current_user)):
    return {"available": xray_model_available()}
