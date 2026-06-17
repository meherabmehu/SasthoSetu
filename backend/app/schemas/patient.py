from datetime import date
from enum import Enum

from pydantic import BaseModel
from pydantic import Field
from pydantic import constr


class GenderEnum(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class BloodGroupEnum(str, Enum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"


class PatientCreate(BaseModel):

    date_of_birth: date

    gender: GenderEnum

    blood_group: BloodGroupEnum

    height_cm: float = Field(
        gt=0,
        le=300
    )

    weight_kg: float = Field(
        gt=0,
        le=500
    )

    emergency_contact: constr(
        pattern=r"^\d{11}$"
    )

    address: str