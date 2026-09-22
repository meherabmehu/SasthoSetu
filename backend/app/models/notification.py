import uuid
from datetime import datetime, timezone

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import false
from sqlalchemy import func

from app.models.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=False
    )

    title = Column(
        String,
        nullable=False
    )

    message = Column(
        String,
        nullable=False
    )

    is_read = Column(
        Boolean,
        default=False,
        server_default=false(),
    )

    # When it arrived, so the list can be shown newest first. Stamped by the
    # client rather than the database: the server default only carries whole
    # seconds, and two notifications written inside one second then sort in a
    # random order.
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
