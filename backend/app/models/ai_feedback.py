import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import Boolean
from sqlalchemy import Integer
from sqlalchemy import ForeignKey

from app.models.base import Base


class AIFeedback(Base):
    __tablename__ = "ai_feedback"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=True
    )

    feature = Column(
        String,
        nullable=False
    )

    input_text = Column(
        Text,
        nullable=True
    )

    corrected_level = Column(
        Integer,
        nullable=True
    )

    correct = Column(
        Boolean,
        nullable=True
    )

    comment = Column(
        Text,
        nullable=True
    )
