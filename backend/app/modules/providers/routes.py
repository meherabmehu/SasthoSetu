from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query

from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import get_current_user, require_admin

from app.schemas.provider import (
    ConsentUpdate,
    LabOrderCreate,
    LabOrderStatusUpdate,
    LabResultUpload,
    LabTestCreate,
    ProviderCreate,
    StockUpsert,
)

from app.modules.providers.service import (
    add_lab_test_service,
    create_lab_order_service,
    create_provider_service,
    get_order_service,
    list_lab_tests_service,
    list_patient_orders_service,
    list_provider_orders_service,
    list_providers_service,
    search_stock_service,
    set_consent_service,
    update_order_status_service,
    upload_result_service,
    upsert_stock_service,
    verify_provider_service,
)

router = APIRouter()


@router.post("/providers")
def create_provider(
    payload: ProviderCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)
    return create_provider_service(payload, db)


@router.get("/providers")
def list_providers(
    provider_type: str | None = None,
    district: str | None = None,
    verified_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return list_providers_service(
        db,
        provider_type=provider_type,
        district=district,
        verified_only=verified_only,
        limit=limit,
        offset=offset,
    )


@router.patch("/providers/{provider_id}/verify")
def verify_provider(
    provider_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)
    return verify_provider_service(provider_id, db)


@router.post("/providers/{provider_id}/tests")
def add_lab_test(
    provider_id: str,
    payload: LabTestCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return add_lab_test_service(provider_id, payload, current_user, db)


@router.get("/lab-tests")
def list_lab_tests(
    provider_id: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return list_lab_tests_service(db, provider_id=provider_id, search=search)


@router.post("/lab-orders")
def create_lab_order(
    payload: LabOrderCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return create_lab_order_service(payload, current_user, db)


@router.get("/lab-orders/patient/{patient_user_id}")
def list_patient_orders(
    patient_user_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_patient_orders_service(patient_user_id, current_user, db)


@router.get("/lab-orders/provider/{provider_id}")
def list_provider_orders(
    provider_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_provider_orders_service(provider_id, current_user, db)


@router.get("/lab-orders/{order_id}")
def get_order(
    order_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_order_service(order_id, current_user, db)


@router.patch("/lab-orders/{order_id}/status")
def update_order_status(
    order_id: str,
    payload: LabOrderStatusUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return update_order_status_service(order_id, payload, current_user, db)


@router.post("/lab-orders/{order_id}/result")
def upload_result(
    order_id: str,
    payload: LabResultUpload,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return upload_result_service(order_id, payload, current_user, db)


@router.patch("/lab-orders/{order_id}/consent")
def set_consent(
    order_id: str,
    payload: ConsentUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return set_consent_service(order_id, payload, current_user, db)


@router.post("/providers/{provider_id}/stock")
def upsert_stock(
    provider_id: str,
    payload: StockUpsert,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return upsert_stock_service(provider_id, payload, current_user, db)


@router.get("/pharmacies/search")
def search_stock(
    medicine: str = Query(min_length=2, max_length=120),
    district: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return search_stock_service(db, medicine=medicine, district=district)
