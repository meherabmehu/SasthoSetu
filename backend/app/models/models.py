# -*- coding: utf-8 -*-
"""SasthoSetu ORM models (portable across SQLite dev / PostgreSQL prod)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Integer, JSON,
                        String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    full_name: Mapped[str] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="patient")  # patient|doctor|admin
    language_pref: Mapped[str] = mapped_column(String(5), default="bn")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    doctor_profile: Mapped["DoctorProfile | None"] = relationship(
        back_populates="user", uselist=False)


class Hospital(Base):
    __tablename__ = "hospitals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(10), unique=True)   # H001...
    name: Mapped[str] = mapped_column(String(160))
    area: Mapped[str] = mapped_column(String(80))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    emergency: Mapped[bool] = mapped_column(Boolean, default=True)
    general_beds: Mapped[int] = mapped_column(Integer, default=0)
    icu_beds: Mapped[int] = mapped_column(Integer, default=0)


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    code: Mapped[str] = mapped_column(String(10), unique=True)   # D001...
    specialty: Mapped[str] = mapped_column(String(60), index=True)
    bmdc_reg_no: Mapped[str] = mapped_column(String(20), unique=True)
    bmdc_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    hospital_id: Mapped[str | None] = mapped_column(
        ForeignKey("hospitals.id"), nullable=True)
    consult_fee_bdt: Mapped[int] = mapped_column(Integer, default=500)
    teleconsult_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rating: Mapped[float] = mapped_column(Float, default=4.5)
    experience_years: Mapped[int] = mapped_column(Integer, default=5)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    user: Mapped[User] = relationship(back_populates="doctor_profile")
    hospital: Mapped[Hospital | None] = relationship()
    availability: Mapped[list["DoctorAvailability"]] = relationship(
        back_populates="doctor")


class DoctorAvailability(Base):
    __tablename__ = "doctor_availability"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctor_profiles.id"))
    weekday: Mapped[int] = mapped_column(Integer)          # 0=Mon .. 6=Sun
    slot_time: Mapped[str] = mapped_column(String(5))      # "18:00"
    mode: Mapped[str] = mapped_column(String(10), default="both")  # tele|visit|both

    doctor: Mapped[DoctorProfile] = relationship(back_populates="availability")


class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctor_profiles.id"),
                                           index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime)
    mode: Mapped[str] = mapped_column(String(10), default="visit")  # tele|visit
    status: Mapped[str] = mapped_column(String(15), default="booked")
    # booked | completed | cancelled | no_show
    triage_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class MedicalRecord(Base):
    __tablename__ = "medical_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    doctor_id: Mapped[str | None] = mapped_column(
        ForeignKey("doctor_profiles.id"), nullable=True)
    record_type: Mapped[str] = mapped_column(String(30), default="consultation")
    title: Mapped[str] = mapped_column(String(160))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    file_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Prescription(Base):
    __tablename__ = "prescriptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    appointment_id: Mapped[str | None] = mapped_column(
        ForeignKey("appointments.id"), nullable=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctor_profiles.id"))
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    advice: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_days: Mapped[int] = mapped_column(Integer, default=30)
    signature: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ai_interaction_report: Mapped[dict] = mapped_column(JSON, default=dict)
    dispensed_at: Mapped[datetime | None] = mapped_column(DateTime,
                                                          nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    items: Mapped[list["PrescriptionItem"]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan")


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    prescription_id: Mapped[str] = mapped_column(ForeignKey("prescriptions.id"))
    drug_name: Mapped[str] = mapped_column(String(120))
    dosage: Mapped[str] = mapped_column(String(60))        # "500 mg"
    frequency: Mapped[str] = mapped_column(String(60))     # "1+0+1"
    duration_days: Mapped[int] = mapped_column(Integer, default=5)
    instructions: Mapped[str | None] = mapped_column(String(200), nullable=True)

    prescription: Mapped[Prescription] = relationship(back_populates="items")


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="info")
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AIFeedback(Base):
    __tablename__ = "ai_feedback"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"),
                                                nullable=True)
    feature: Mapped[str] = mapped_column(String(30))       # triage|surge|...
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_output: Mapped[dict] = mapped_column(JSON, default=dict)
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    corrected_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
