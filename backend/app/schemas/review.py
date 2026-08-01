from typing import Literal

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    """A review is always anchored to a specific appointment.

    There is no field for a free-floating review: the appointment reference is
    what makes the feedback provable, so it is required rather than optional.
    """

    appointment_id: str
    rating: int = Field(ge=1, le=5)
    rating_explanation: int | None = Field(default=None, ge=1, le=5)
    rating_punctuality: int | None = Field(default=None, ge=1, le=5)
    rating_respect: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)
    language: Literal["bn", "en"] = "bn"


class ReviewHide(BaseModel):
    reason: str = Field(min_length=3, max_length=300)
