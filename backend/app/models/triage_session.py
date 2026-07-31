import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Integer
from sqlalchemy import Float
from sqlalchemy import Text
from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import false
from sqlalchemy import func

from app.models.base import Base


class TriageSession(Base):
    """A stored triage assessment.

    Persisting every assessment is what turns triage from a stateless helper
    into clinical evidence: it lets a doctor see what the patient was told
    before the consultation, and supplies the labelled history the retraining
    loop needs.
    """

    __tablename__ = "triage_sessions"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    patient_id = Column(
        String,
        ForeignKey("patients.id"),
        nullable=True
    )

    user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=True
    )

    input_text = Column(
        Text,
        nullable=False
    )

    language = Column(
        String,
        nullable=True
    )

    age_years = Column(
        Integer,
        nullable=True
    )

    temperature_c = Column(
        Float,
        nullable=True
    )

    engine = Column(
        String,
        nullable=False,
        default="rules",
        server_default="rules",
    )

    model_version = Column(
        String,
        nullable=True
    )

    triage_level = Column(
        String,
        nullable=False
    )

    severity_level = Column(
        Integer,
        nullable=True
    )

    possible_condition = Column(
        String,
        nullable=True
    )

    recommended_specialty = Column(
        String,
        nullable=True
    )

    confidence = Column(
        Float,
        nullable=True
    )

    matched_symptoms = Column(
        JSON,
        nullable=True
    )

    safety_flags = Column(
        JSON,
        nullable=True
    )

    latitude = Column(
        Float,
        nullable=True
    )

    longitude = Column(
        Float,
        nullable=True
    )

    # Clinician review of the assessment, written back by the feedback loop.
    reviewed_by = Column(
        String,
        ForeignKey("doctors.id"),
        nullable=True
    )

    clinician_level = Column(
        Integer,
        nullable=True
    )

    review_note = Column(
        Text,
        nullable=True
    )

    was_overridden = Column(
        Boolean,
        default=False,
        server_default=false(),
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
