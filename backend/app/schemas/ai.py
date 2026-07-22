from pydantic import BaseModel
from pydantic import Field


class DrugCheckRequest(BaseModel):

    drugs: list[str] = Field(min_length=2, max_length=20)


class SurveillanceQuery(BaseModel):

    district: str | None = None
    disease: str | None = None
    weeks: int = 26


class AIFeedbackCreate(BaseModel):

    feature: str = Field(pattern="^(triage|surge|surveillance|drug_safety)$")
    input_text: str | None = None
    correct: bool | None = None
    corrected_level: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = None
