from datetime import date

from pydantic import BaseModel
from pydantic import Field


class MedicalRecordCreate(BaseModel):

    patient_id: str

    diagnosis: str = Field(
        min_length=3,
        max_length=500
    )

    notes: str | None = None

    record_date: date