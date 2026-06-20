from enum import Enum

from pydantic import BaseModel


class AppointmentStatusEnum(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatusEnum