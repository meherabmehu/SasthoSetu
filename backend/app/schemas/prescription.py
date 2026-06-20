from pydantic import BaseModel
from pydantic import Field


class PrescriptionCreate(BaseModel):

    appointment_id: str

    medicine_name: str = Field(
        min_length=2,
        max_length=200
    )

    dosage: str = Field(
        min_length=1,
        max_length=100
    )

    duration: str = Field(
        min_length=1,
        max_length=100
    )

    instructions: str | None = None