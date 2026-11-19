from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import require_admin
from app.core.config import settings
from app.ai.observability import telemetry_summary
from app.integrations.providers import provider_readiness

from app.modules.admin.service import (
    get_all_users_service,
    get_user_by_id_service,
    disable_user_service,
    enable_user_service,
    delete_user_service
)

router = APIRouter()


@router.get(
    "/admin/operations/summary",
    dependencies=[Depends(require_admin)],
)
def operations_summary(
    hours: int = 24,
    db: Session = Depends(get_db),
):
    """Admin-only, de-identified production-readiness dashboard data."""
    hours = min(max(hours, 1), 168)
    return {
        "environment": settings.app_env,
        "ai_telemetry": telemetry_summary(db, hours=hours),
        "providers": provider_readiness(),
        "demo_notice": (
            "This deployment is a sandbox: no payment, SMS or IVR is delivered, "
            "and AI outputs are not diagnoses."
        ),
    }


@router.get(
    "/admin/users",
    dependencies=[Depends(require_admin)],
)
def get_all_users(
    db: Session = Depends(get_db)
):
    return get_all_users_service(
        db=db
    )


@router.get(
    "/admin/users/{user_id}",
    dependencies=[Depends(require_admin)],
)
def get_user_by_id(
    user_id: str,
    db: Session = Depends(get_db)
):
    return get_user_by_id_service(
        user_id=user_id,
        db=db
    )


@router.patch(
    "/admin/users/{user_id}/disable",
    dependencies=[Depends(require_admin)],
)
def disable_user(
    user_id: str,
    db: Session = Depends(get_db)
):
    return disable_user_service(
        user_id=user_id,
        db=db
    )


@router.patch(
    "/admin/users/{user_id}/enable",
    dependencies=[Depends(require_admin)],
)
def enable_user(
    user_id: str,
    db: Session = Depends(get_db)
):
    return enable_user_service(
        user_id=user_id,
        db=db
    )


@router.delete(
    "/admin/users/{user_id}",
    dependencies=[Depends(require_admin)],
)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db)
):
    return delete_user_service(
        user_id=user_id,
        db=db
    )
