from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# Clinical thermometers in Bangladesh are overwhelmingly marked in
# Fahrenheit, so "101" is the natural thing for a patient to type. The two
# scales do not overlap in any survivable range — 45 °C is already fatal and
# 45 °F is hypothermic well beyond consciousness — so a value above the
# Celsius ceiling can only be Fahrenheit, and is converted rather than
# rejected. Anything outside both ranges is still refused.
_CELSIUS_MAX = 45.0
_FAHRENHEIT_MIN = 86.0
_FAHRENHEIT_MAX = 113.0


def to_celsius(value) -> float | None:
    """Normalise a temperature reading to Celsius, accepting either scale."""

    if value is None or value == "":
        return None

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        raise ValueError("temperature must be a number") from None

    if numeric > _CELSIUS_MAX:
        if _FAHRENHEIT_MIN <= numeric <= _FAHRENHEIT_MAX:
            return round((numeric - 32.0) * 5.0 / 9.0, 1)
        raise ValueError("temperature must be 30-45 °C or 86-113 °F")

    if numeric < 30:
        raise ValueError("temperature must be 30-45 °C or 86-113 °F")

    return numeric


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
    # Validated by the converter below rather than by ge/le, so a Fahrenheit
    # reading is accepted instead of producing a bare "less than or equal to
    # 45" message that never mentions the unit.
    temperature_c: float | None = None

    @field_validator("temperature_c", mode="before")
    @classmethod
    def accept_fahrenheit(cls, value):
        return to_celsius(value)

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
    possible_condition_bn: str = ""
    recommended_specialty: str
    confidence: int = Field(ge=0, le=100)
    matched_symptoms: list[str]
    safety_flags: list[str]
    # Ranked possible conditions. Always a list of possibilities, never a
    # single asserted diagnosis.
    differential: list[dict] = []
    # Which layer contributed what: rules alone, or rules plus model.
    understanding: dict = {}
    advice: str
    advice_bn: str = ""
    disclaimer: str
    disclaimer_bn: str = ""
