from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import get_current_user, require_self_or_admin

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
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Notifications are personal correspondence, so unlike a clinical record
    # a treating doctor has no claim to them.
    require_self_or_admin(user_id, current_user)
    return get_notifications_service(
        user_id=user_id,
        db=db
    )


@router.patch(
    "/notifications/{notification_id}/read"
)
def mark_notification_read(
    notification_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return mark_notification_read_service(
        notification_id=notification_id,
        current_user=current_user,
        db=db
    )