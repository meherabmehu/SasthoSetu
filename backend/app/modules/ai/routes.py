from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import Form
from fastapi import HTTPException
from fastapi import UploadFile
from fastapi import Request
import time

from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import get_current_user
from app.core.security import require_admin
from app.ai.observability import record_event
from app.ai.observability import telemetry_summary

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
from app.ai.eye_service import (
    EyeModelError,
    assess_eye_photo,
    model_available as eye_model_available,
)
from app.ai.oral_service import (
    OralModelError,
    assess_oral_photo,
    model_available as oral_model_available,
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
    http_request: Request,
    request: TriageRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    started = time.perf_counter()
    result = ml_triage_service(request.symptoms, age=request.age_years)
    record_event(
        db,
        feature="triage",
        model_version=result.get("model_version", "banglamed-triage-v1.1"),
        outcome=str(result.get("severity_label", "unknown")),
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
        low_confidence=bool(result.get("low_confidence")),
        age_years=request.age_years,
        request_id=getattr(http_request.state, "request_id", None) if http_request else None,
    )
    return result


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
        query.district, query.disease, query.weeks, query.source)


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
    http_request: Request,
    image: UploadFile = File(...),
    age_years: int | None = Form(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
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
        started = time.perf_counter()
        result = assess_skin_image(payload, age=age_years)
        record_event(
            db,
            feature="skin",
            model_version=result.get("model_version", "sasthosetu-skin-v1.0"),
            outcome=result.get("band", "unknown"),
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            low_confidence=bool(result.get("low_confidence")),
            age_years=age_years,
            request_id=getattr(http_request.state, "request_id", None) if http_request else None,
        )
        return result
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
    http_request: Request,
    image: UploadFile = File(...),
    age_years: int | None = Form(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Screen one chest film.

    A screen, not a report. It cannot rule pneumonia out, and the response
    says so in both languages.
    """
    payload = await image.read()

    if not payload:
        raise HTTPException(status_code=400, detail="No image was uploaded")

    try:
        started = time.perf_counter()
        result = assess_chest_xray(payload, age=age_years)
        record_event(
            db,
            feature="xray",
            model_version=result.get("model_version", "sasthosetu-cxr-v1.0"),
            outcome=result.get("band", "unknown"),
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            low_confidence=bool(result.get("low_confidence")),
            age_years=age_years,
            request_id=getattr(http_request.state, "request_id", None) if http_request else None,
        )
        return result
    except XrayModelError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get(
    "/ai/xray-check/status",
    summary="Whether the chest X-ray model is built and servable",
)
def xray_check_status(current_user=Depends(get_current_user)):
    from app.ai.xray_service import _tb_bundle
    return {"available": xray_model_available(), "tuberculosis_available": _tb_bundle() is not None,
            "mode": "demo", "clinically_validated": False}


@router.post(
    "/ai/eye-check",
    summary="Screen a retina photograph for diabetic retinopathy",
)
async def eye_check(
    http_request: Request,
    image: UploadFile = File(...),
    age_years: int | None = Form(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Screen one fundus photograph.

    A screen, not an eye examination. It cannot rule retinopathy out, and
    the response says so in both languages.
    """
    payload = await image.read()

    if not payload:
        raise HTTPException(status_code=400, detail="No image was uploaded")

    try:
        started = time.perf_counter()
        result = assess_eye_photo(payload, age=age_years)
        record_event(
            db,
            feature="retina",
            model_version=result.get("model_version", "sasthosetu-dr-v1.0"),
            outcome=result.get("band", "unknown"),
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            low_confidence=bool(result.get("low_confidence")),
            age_years=age_years,
            request_id=getattr(http_request.state, "request_id", None) if http_request else None,
        )
        return result
    except EyeModelError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get(
    "/ai/eye-check/status",
    summary="Whether the retinopathy model is built and servable",
)
def eye_check_status(current_user=Depends(get_current_user)):
    return {"available": eye_model_available()}


@router.post(
    "/ai/oral-check",
    summary="Screen a mouth photograph for signs of oral cancer",
)
async def oral_check(
    http_request: Request,
    image: UploadFile = File(...),
    age_years: int | None = Form(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Screen one photograph of the inside of a mouth.

    A screen, not a diagnosis. It cannot rule cancer out, and the response
    says so in both languages.
    """
    payload = await image.read()

    if not payload:
        raise HTTPException(status_code=400, detail="No image was uploaded")

    try:
        started = time.perf_counter()
        result = assess_oral_photo(payload, age=age_years)
        record_event(
            db,
            feature="oral",
            model_version=result.get("model_version", "sasthosetu-oral-v1.0"),
            outcome=result.get("band", "unknown"),
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            low_confidence=bool(result.get("low_confidence")),
            age_years=age_years,
            request_id=getattr(http_request.state, "request_id", None) if http_request else None,
        )
        return result
    except OralModelError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get(
    "/ai/oral-check/status",
    summary="Whether the oral cancer model is built and servable",
)
def oral_check_status(current_user=Depends(get_current_user)):
    return {"available": oral_model_available()}


@router.get(
    "/ai/telemetry/summary",
    dependencies=[Depends(require_admin)],
)
def ai_telemetry_summary(
    hours: int = 24,
    db: Session = Depends(get_db),
):
    hours = min(max(hours, 1), 168)
    return telemetry_summary(db, hours=hours)


@router.get("/ai/data-sources/status")
def ai_data_sources_status(current_user=Depends(get_current_user)):
    return {
        "triage": {
            "status": "synthetic_and_external_vocab",
            "clinically_validated": False,
            "replacement_required": "clinician-labelled Bangla corpus",
        },
        "surge": {
            "status": "synthetic_demo",
            "is_live": False,
            "clinically_validated": False,
        },
        "surveillance": {
            "status": "historical_dengue_estimates",
            "is_live": False,
            "not_for_real_time_alerting": True,
        },
        "imaging": {
            "status": "research_demo",
            "clinically_validated": False,
            "licensing_review_required": True,
        },
        "llm": {
            "configured": bool(__import__("os").environ.get("LLM_API_KEY")),
            "role": "symptom_normalisation_only",
            "deterministic_fallback": True,
        },
    }
