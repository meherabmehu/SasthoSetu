from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TriageLevel(str, Enum):
    SELF_CARE = "SELF_CARE"
    TELECONSULT = "TELECONSULT"
    GP_VISIT = "GP_VISIT"
    SPECIALIST = "SPECIALIST"
    EMERGENCY = "EMERGENCY"


class TriageRequest(BaseModel):
    symptoms: str = Field(min_length=3, max_length=2000)
    language: Literal["auto", "bn", "en"] = "auto"
    age_years: int | None = Field(default=None, ge=0, le=120)
    temperature_c: float | None = Field(default=None, ge=30, le=45)

    @field_validator("symptoms")
    @classmethod
    def symptoms_must_contain_text(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not any(character.isalpha() for character in cleaned):
            raise ValueError("symptoms must contain descriptive text")
        return cleaned


class TriageResponse(BaseModel):
    triage_level: TriageLevel
    possible_condition: str
    recommended_specialty: str
    confidence: int = Field(ge=0, le=100)
    matched_symptoms: list[str]
    safety_flags: list[str]
    advice: str
    disclaimer: str
