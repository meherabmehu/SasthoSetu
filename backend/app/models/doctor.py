import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Integer
from sqlalchemy import Float
from sqlalchemy import Boolean
from sqlalchemy import ForeignKey

from app.models.base import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=False,
        unique=True
    )

    bmdc_number = Column(
        String,
        unique=True,
        nullable=False
    )

    specialization = Column(
        String,
        nullable=False
    )

    experience_years = Column(
        Integer,
        nullable=False
    )

    consultation_fee = Column(
        Float,
        nullable=False
    )

    hospital_name = Column(
        String,
        nullable=False
    )

    bio = Column(
        String,
        nullable=True
    )

    verification_status = Column(
        Boolean,
        default=False
    )