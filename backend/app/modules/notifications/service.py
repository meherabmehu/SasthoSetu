from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.models.notification import Notification


def create_notification(
    user_id: str,
    title: str,
    message: str,
    db: Session
):

    notification = Notification(
        user_id=user_id,
        title=title,
        message=message
    )

    db.add(notification)
    db.commit()


def get_notifications_service(
    user_id: str,
    db: Session
):

    return (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id
        )
        .all()
    )


def mark_notification_read_service(
    notification_id: str,
    db: Session,
    current_user: dict | None = None
):

    notification = (
        db.query(Notification)
        .filter(
            Notification.id
            == notification_id
        )
        .first()
    )

    if not notification:
        raise HTTPException(
            status_code=404,
            detail="Notification not found"
        )

    # Only the recipient may mark their own notification read. Without this a
    # caller could walk notification ids and silently clear someone else's.
    if current_user is not None:
        is_owner = notification.user_id == current_user.get("user_id")
        if not is_owner and current_user.get("role") != "ADMIN":
            raise HTTPException(
                status_code=403,
                detail="You cannot modify another user's notification"
            )

    notification.is_read = True

    db.commit()

    return {
        "message": "Notification marked as read"
    }