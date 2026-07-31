from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import get_current_user

from app.schemas.clinical import (
    ConsultationStart,
    ConsultationUpdate,
    DispenseRequest,
    MessageCreate,
    PrescriptionCreateRequest,
    PrescriptionVerifyRequest,
)

from app.modules.consultations.service import (
    cancel_prescription_service,
    close_consultation_service,
    dispense_prescription_service,
    get_consultation_service,
    issue_prescription_service,
    list_messages_service,
    list_patient_prescriptions_service,
    post_message_service,
    start_consultation_service,
    update_consultation_service,
    verify_prescription_service,
)

router = APIRouter()


@router.post("/consultations")
def start_consultation(
    payload: ConsultationStart,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return start_consultation_service(payload, current_user, db)


@router.get("/consultations/{consultation_id}")
def get_consultation(
    consultation_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_consultation_service(consultation_id, current_user, db)


@router.patch("/consultations/{consultation_id}")
def update_consultation(
    consultation_id: str,
    payload: ConsultationUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return update_consultation_service(consultation_id, payload, current_user, db)


@router.post("/consultations/{consultation_id}/close")
def close_consultation(
    consultation_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return close_consultation_service(consultation_id, current_user, db)


@router.post("/consultations/{consultation_id}/messages")
def post_message(
    consultation_id: str,
    payload: MessageCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return post_message_service(consultation_id, payload, current_user, db)


@router.get("/consultations/{consultation_id}/messages")
def list_messages(
    consultation_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_messages_service(consultation_id, current_user, db)


@router.post("/prescriptions/issue")
def issue_prescription(
    payload: PrescriptionCreateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return issue_prescription_service(payload, current_user, db)


@router.post("/prescriptions/verify")
def verify_prescription(
    payload: PrescriptionVerifyRequest,
    db: Session = Depends(get_db),
):
    """Pharmacy endpoint: confirm a prescription is genuine before dispensing."""
    return verify_prescription_service(payload, db)


@router.post("/prescriptions/dispense")
def dispense_prescription(
    payload: DispenseRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return dispense_prescription_service(payload, current_user, db)


@router.post("/prescriptions/{prescription_id}/cancel")
def cancel_prescription(
    prescription_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return cancel_prescription_service(prescription_id, current_user, db)


@router.get("/prescriptions/records/{patient_user_id}")
def list_patient_prescriptions(
    patient_user_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_patient_prescriptions_service(patient_user_id, current_user, db)
