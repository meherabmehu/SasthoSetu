import uuid

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import func

from app.models.base import Base


class AIInferenceEvent(Base):
    __tablename__ = "ai_inference_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    feature = Column(String(32), nullable=False, index=True)
    model_version = Column(String(64), nullable=False)
    outcome = Column(String(32), nullable=False)
    status_code = Column(Integer, nullable=False, default=200)
    latency_ms = Column(Float, nullable=False, default=0.0)
    fallback_used = Column(Boolean, nullable=False, default=False)
    low_confidence = Column(Boolean, nullable=False, default=False)
    age_band = Column(String(16), nullable=True)
    request_id = Column(String(32), nullable=True)
