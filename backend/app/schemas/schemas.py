# -*- coding: utf-8 -*-
"""Pydantic schemas for all SasthoSetu endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- auth ----------------------------------------------------------------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str
    phone: Optional[str] = None
    role: str = Field(default="patient", pattern="^(patient|doctor)$")
    language_pref: str = "bn"


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
    full_name: str


class UserOut(ORM):
    id: str
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    role: str
    language_pref: str
    created_at: datetime


# ---- doctors / hospitals -------------------------------------------------
class HospitalOut(ORM):
    id: str
    code: str
    name: str
    area: str
    lat: float
    lng: float
    emergency: bool
    general_beds: int
    icu_beds: int


class DoctorOut(ORM):
    id: str
    code: str
    specialty: str
    bmdc_reg_no: str
    bmdc_verified: bool
    consult_fee_bdt: int
    teleconsult_enabled: bool
    rating: float
    experience_years: int
    full_name: Optional[str] = None
    hospital_name: Optional[str] = None
    next_slots: list[str] = []
    match_score: Optional[float] = None


class AvailabilityIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    slot_time: str
    mode: str = Field(default="both", pattern="^(tele|visit|both)$")


class AvailabilityOut(ORM):
    id: str
    weekday: int
    slot_time: str
    mode: str


# ---- appointments --------------------------------------------------------
class AppointmentIn(BaseModel):
    doctor_id: str
    scheduled_at: datetime
    mode: str = Field(default="visit", pattern="^(tele|visit)$")
    triage_ref: Optional[str] = None
    notes: Optional[str] = None


class AppointmentOut(ORM):
    id: str
    patient_id: str
    doctor_id: str
    scheduled_at: datetime
    mode: str
    status: str
    triage_ref: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


# ---- medical records -----------------------------------------------------
class MedicalRecordIn(BaseModel):
    record_type: str = "consultation"
    title: str
    details: dict = {}
    patient_id: Optional[str] = None       # doctors/admins may set


class MedicalRecordOut(ORM):
    id: str
    patient_id: str
    doctor_id: Optional[str] = None
    record_type: str
    title: str
    details: dict
    file_path: Optional[str] = None
    created_at: datetime


# ---- prescriptions -------------------------------------------------------
class RxItemIn(BaseModel):
    drug_name: str
    dosage: str = "500 mg"
    frequency: str = "1+0+1"
    duration_days: int = 5
    instructions: Optional[str] = None


class PrescriptionIn(BaseModel):
    patient_id: str
    appointment_id: Optional[str] = None
    diagnosis: Optional[str] = None
    advice: Optional[str] = None
    valid_days: int = 30
    items: list[RxItemIn]


class RxItemOut(ORM):
    id: str
    drug_name: str
    dosage: str
    frequency: str
    duration_days: int
    instructions: Optional[str] = None


class PrescriptionOut(ORM):
    id: str
    patient_id: str
    doctor_id: str
    diagnosis: Optional[str] = None
    advice: Optional[str] = None
    valid_days: int
    signature: Optional[str] = None
    ai_interaction_report: dict = {}
    dispensed_at: Optional[datetime] = None
    created_at: datetime
    items: list[RxItemOut] = []


class RxVerifyIn(BaseModel):
    prescription_id: str
    signature: str
    mark_dispensed: bool = False


class RxVerifyOut(BaseModel):
    is_valid: bool
    is_expired: bool
    was_already_dispensed: bool
    flagged_interactions: list[dict] = []
    prescription: Optional[PrescriptionOut] = None
    reason: Optional[str] = None


# ---- notifications -------------------------------------------------------
class NotificationOut(ORM):
    id: str
    kind: str
    title: str
    body: str
    is_read: bool
    created_at: datetime


# ---- AI ------------------------------------------------------------------
class TriageIn(BaseModel):
    notes: str = Field(min_length=2, max_length=2000)
    age: Optional[int] = Field(default=None, ge=0, le=120)
    language_hint: Optional[str] = None


class DrugCheckIn(BaseModel):
    drugs: list[str] = Field(min_length=2, max_length=20)


class FeedbackIn(BaseModel):
    feature: str = Field(pattern="^(triage|surge|surveillance|drug_safety)$")
    input_text: Optional[str] = None
    model_output: dict = {}
    correct: Optional[bool] = None
    corrected_level: Optional[int] = Field(default=None, ge=1, le=5)
    comment: Optional[str] = None
