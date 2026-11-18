from pydantic import BaseModel
from pydantic import Field
from typing import Literal


class DrugCheckRequest(BaseModel):

    drugs: list[str] = Field(min_length=2, max_length=20)


class SurveillanceQuery(BaseModel):

    district: str | None = None
    disease: str | None = None
    weeks: int = Field(default=26, ge=1, le=160)
    source: Literal[
        "synthetic_demo", "bangladesh_dengue_estimates_2022_2024"
    ] = "synthetic_demo"


class AIFeedbackCreate(BaseModel):

    feature: str = Field(pattern="^(triage|surge|surveillance|drug_safety)$")
    input_text: str | None = None
    correct: bool | None = None
    corrected_level: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = None
