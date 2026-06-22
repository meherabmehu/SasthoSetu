from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.modules.notifications.service import (
    get_notifications_service,
    mark_notification_read_service
)

router = APIRouter()


@router.get(
    "/notifications/{user_id}"
)
def get_notifications(
    user_id: str,
    db: Session = Depends(get_db)
):
    return get_notifications_service(
        user_id=user_id,
        db=db
    )


@router.patch(
    "/notifications/{notification_id}/read"
)
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db)
):
    return mark_notification_read_service(
        notification_id=notification_id,
        db=db
    )