from datetime import date

from pydantic import BaseModel
from pydantic import Field


class DoctorAvailabilityCreate(BaseModel):

    available_date: date

    start_time: str = Field(
        min_length=3,
        max_length=20
    )

    end_time: str = Field(
        min_length=3,
        max_length=20
    )