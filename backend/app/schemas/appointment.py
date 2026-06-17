from enum import Enum
from datetime import date

from pydantic import BaseModel
from pydantic import Field


class AppointmentStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class AppointmentCreate(BaseModel):

    doctor_id: str

    appointment_date: date

    appointment_time: str

    reason: str = Field(
        min_length=5,
        max_length=500
    )