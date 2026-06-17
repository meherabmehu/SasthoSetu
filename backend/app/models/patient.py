import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Float
from sqlalchemy import Date
from sqlalchemy import ForeignKey

from app.models.base import Base


class Patient(Base):
    __tablename__ = "patients"

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

    date_of_birth = Column(
        Date,
        nullable=False
    )

    gender = Column(
        String,
        nullable=False
    )

    blood_group = Column(
        String,
        nullable=False
    )

    height_cm = Column(
        Float,
        nullable=False
    )

    weight_kg = Column(
        Float,
        nullable=False
    )

    emergency_contact = Column(
        String,
        nullable=False
    )

    address = Column(
        String,
        nullable=False
    )