from typing import Literal

from pydantic import BaseModel, Field


class SmsInbound(BaseModel):
    """An inbound SMS forwarded by the gateway."""

    phone: str | None = Field(default=None, max_length=20)
    text: str = Field(min_length=3, max_length=480)
    language: Literal["bn", "en"] = "bn"
    age_years: int | None = Field(default=None, ge=0, le=120)


class IvrSelection(BaseModel):
    node: str = Field(default="root", max_length=32)
    digit: str = Field(min_length=1, max_length=1, pattern=r"^[0-9*#]$")
    language: Literal["bn", "en"] = "bn"
    age_years: int | None = Field(default=None, ge=0, le=120)
    caller_id: str | None = Field(default=None, max_length=20)


class ChwAssessment(BaseModel):
    """One household assessment captured during a home visit."""

    # Set by the tablet so a retried batch can be reconciled without
    # creating duplicates.
    client_reference: str = Field(min_length=1, max_length=64)
    symptoms: str = Field(min_length=3, max_length=2000)
    language: Literal["bn", "en"] = "bn"
    age_years: int | None = Field(default=None, ge=0, le=120)
    temperature_c: float | None = Field(default=None, ge=30, le=45)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    household_id: str | None = Field(default=None, max_length=64)


class ChwBatch(BaseModel):
    assessments: list[ChwAssessment] = Field(min_length=1, max_length=200)
