from pydantic import BaseModel
from pydantic import Field
from pydantic import constr


class DoctorCreate(BaseModel):

    bmdc_number: constr(
        min_length=4,
        max_length=50
    )

    specialization: str

    experience_years: int = Field(
        ge=0,
        le=70
    )

    consultation_fee: float = Field(
        gt=0
    )

    hospital_name: str

    bio: str | None = None