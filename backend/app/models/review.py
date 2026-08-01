import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Integer
from sqlalchemy import Float
from sqlalchemy import Text
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import UniqueConstraint
from sqlalchemy import false
from sqlalchemy import func

from app.models.base import Base


class DoctorReview(Base):
    """A patient review that is provably tied to a real completed encounter.

    Fake reviews are the failure mode that destroys the usefulness of a rating
    system, so a review here cannot be written at all unless the platform can
    prove the visit happened. Every row references a specific completed
    appointment, and the database enforces one review per appointment. There
    is no free-floating "write a review" path.

    Proof strength is recorded rather than assumed, because not all evidence is
    equal: a consultation the doctor signed off is stronger evidence than an
    appointment merely marked attended. Weaker proof still counts, but counts
    for less in the aggregate score.
    """

    __tablename__ = "doctor_reviews"

    __table_args__ = (
        # One review per appointment. This single constraint is what makes
        # review-farming structurally impossible rather than merely discouraged.
        UniqueConstraint("appointment_id", name="uq_review_per_appointment"),
    )

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    doctor_id = Column(
        String,
        ForeignKey("doctors.id"),
        nullable=False,
        index=True
    )

    patient_id = Column(
        String,
        ForeignKey("patients.id"),
        nullable=False,
        index=True
    )

    appointment_id = Column(
        String,
        ForeignKey("appointments.id"),
        nullable=False
    )

    consultation_id = Column(
        String,
        ForeignKey("consultations.id"),
        nullable=True
    )

    rating = Column(
        Integer,
        nullable=False
    )

    # Sub-scores let a patient say the doctor explained well but ran late,
    # which a single star rating cannot express.
    rating_explanation = Column(
        Integer,
        nullable=True
    )

    rating_punctuality = Column(
        Integer,
        nullable=True
    )

    rating_respect = Column(
        Integer,
        nullable=True
    )

    comment = Column(
        Text,
        nullable=True
    )

    language = Column(
        String,
        nullable=True
    )

    # SIGNED_CONSULTATION | COMPLETED_APPOINTMENT | PRESCRIPTION_DISPENSED
    proof_type = Column(
        String,
        nullable=False
    )

    proof_weight = Column(
        Float,
        nullable=False,
        default=1.0,
        server_default="1.0",
    )

    # Retained so a rating can be recomputed or audited later without guessing
    # what evidence existed at the time.
    proof_reference = Column(
        String,
        nullable=True
    )

    is_verified = Column(
        Boolean,
        default=True,
        server_default="1",
    )

    # Set when a review is withdrawn or found abusive. Hidden rather than
    # deleted, so the audit trail survives.
    is_hidden = Column(
        Boolean,
        default=False,
        server_default=false(),
    )

    hidden_reason = Column(
        String,
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class DoctorRatingSummary(Base):
    """Cached aggregate rating for a doctor.

    Recomputed whenever a review lands. Denormalised because doctor search
    ranks by rating on every query, and recomputing a weighted average across
    all reviews per doctor per search would not hold up.
    """

    __tablename__ = "doctor_rating_summaries"

    doctor_id = Column(
        String,
        ForeignKey("doctors.id"),
        primary_key=True
    )

    average_rating = Column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )

    # Shrunk toward the platform mean so a doctor with one five-star review
    # does not outrank one with fifty averaging 4.7.
    bayesian_rating = Column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )

    review_count = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    verified_review_count = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    average_explanation = Column(Float, nullable=True)
    average_punctuality = Column(Float, nullable=True)
    average_respect = Column(Float, nullable=True)

    updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=func.now(),
        server_default=func.now(),
    )
