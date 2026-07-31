from typing import Literal

from pydantic import BaseModel, Field


class TriageReview(BaseModel):
    clinician_level: int = Field(ge=1, le=5)
    note: str | None = Field(default=None, max_length=1000)


class ConsultationStart(BaseModel):
    appointment_id: str
    triage_session_id: str | None = None
    chief_complaint: str | None = Field(default=None, max_length=2000)


class ConsultationUpdate(BaseModel):
    chief_complaint: str | None = Field(default=None, max_length=2000)
    examination_notes: str | None = Field(default=None, max_length=5000)
    diagnosis: str | None = Field(default=None, max_length=300)
    advice: str | None = Field(default=None, max_length=3000)
    follow_up_date: str | None = Field(default=None, max_length=32)
    investigations: list[str] | None = None


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class PrescriptionLineCreate(BaseModel):
    medicine_name: str = Field(min_length=1, max_length=200)
    strength: str | None = Field(default=None, max_length=64)
    dosage_form: Literal[
        "tablet", "capsule", "syrup", "injection", "inhaler",
        "drops", "cream", "ointment", "suppository", "other",
    ] = "tablet"
    frequency: str = Field(min_length=1, max_length=120)
    duration: str = Field(min_length=1, max_length=120)
    route: Literal["oral", "topical", "intravenous", "intramuscular",
                   "subcutaneous", "inhaled", "rectal", "ophthalmic",
                   "nasal", "other"] = "oral"
    instructions: str | None = Field(default=None, max_length=500)


class PrescriptionCreateRequest(BaseModel):
    consultation_id: str | None = None
    appointment_id: str | None = None
    diagnosis: str | None = Field(default=None, max_length=300)
    advice: str | None = Field(default=None, max_length=3000)
    valid_days: int = Field(default=30, ge=1, le=180)
    items: list[PrescriptionLineCreate] = Field(min_length=1, max_length=30)


class PrescriptionVerifyRequest(BaseModel):
    verification_code: str = Field(min_length=4, max_length=64)
    signature: str | None = Field(default=None, max_length=128)


class DispenseRequest(BaseModel):
    verification_code: str = Field(min_length=4, max_length=64)
    signature: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=500)
