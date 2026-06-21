from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.core.security import (
    require_admin
)

from app.modules.dashboard.service import (
    get_dashboard_stats_service
)

router = APIRouter()


@router.get("/dashboard/stats")
def get_dashboard_stats(
    current_user=Depends(
        require_admin
    ),
    db: Session = Depends(get_db)
):
    return get_dashboard_stats_service(
        db=db
    )