from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query

from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import get_current_user

from app.schemas.rural import (
    ChwBatch,
    IvrSelection,
    SmsInbound,
)

from app.modules.rural.service import (
    chw_batch_service,
    ivr_menu_service,
    ivr_select_service,
    sms_triage_service,
)

router = APIRouter()


@router.post("/rural/sms/triage")
def sms_triage(
    payload: SmsInbound,
    db: Session = Depends(get_db),
):
    """Triage an inbound SMS and return the reply body to send back.

    Unauthenticated by design: it is called by the SMS gateway, and the
    sender is identified by their number rather than a token.
    """
    return sms_triage_service(payload, db)


@router.get("/rural/ivr/menu")
def ivr_menu(
    node: str = Query(default="root", max_length=32),
    language: str = Query(default="bn", pattern="^(bn|en)$"),
):
    return ivr_menu_service(node, language)


@router.post("/rural/ivr/select")
def ivr_select(
    payload: IvrSelection,
    db: Session = Depends(get_db),
):
    return ivr_select_service(payload, db)


@router.post("/rural/chw/batch")
def chw_batch(
    payload: ChwBatch,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit assessments collected offline during home visits."""
    return chw_batch_service(payload, current_user, db)
