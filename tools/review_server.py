"""Isolated, disposable fixture server for browser QA. Never uses the app database.

Run from the repo root: python tools/review_server.py
Only the fixture database under .tmp is written. Uses fixed TEST-ONLY accounts.
"""
# ruff: noqa: E402
import os
import sys
import uuid
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
(ROOT / ".tmp").mkdir(exist_ok=True)
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///" + (
    ROOT / ".tmp" / f"browser-review-{uuid.uuid4().hex}.db").as_posix()
os.environ["ACCOUNT_EMAIL_MODE"] = "demo"
os.environ["SECRET_KEY"] = "browser-fixture-secret-only-not-for-deployment"

from alembic import command
from alembic.config import Config
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.provider import LabTest, Provider
from app.models.user import User

config = Config(str(ROOT / "backend" / "alembic.ini"))
config.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
command.upgrade(config, "head")
with SessionLocal() as db:
    hashed = hash_password("BrowserDemo123!")
    for name, role in [("patient", "PATIENT"), ("other", "PATIENT"), ("doctor", "DOCTOR"),
                       ("admin", "ADMIN"), ("operator", "PATIENT")]:
        if not db.get(User, "qa-" + name):
            db.add(User(id="qa-" + name, full_name="QA " + name, email=f"{name}@qa.example",
                         phone="qa-" + name, password_hash=hashed, role=role))
    db.flush()
    for name in ["patient", "other"]:
        if not db.get(Patient, "qa-" + name):
            db.add(Patient(id="qa-" + name, user_id="qa-" + name, date_of_birth=date(1990, 1, 1),
                            gender="FEMALE", blood_group="B+", height_cm=160, weight_kg=60,
                            emergency_contact="01711111111", address="Dhaka"))
    if not db.get(Doctor, "qa-doctor"):
        db.add(Doctor(id="qa-doctor", user_id="qa-doctor", bmdc_number="QA-ONLY",
                       specialization="Medicine", experience_years=5, consultation_fee=500,
                       hospital_name="QA", verification_status=True))
    db.flush()
    if not db.get(Appointment, "qa-appointment"):
        db.add(Appointment(id="qa-appointment", patient_id="qa-patient", doctor_id="qa-doctor",
                            appointment_date="2099-01-01", appointment_time="10:00", reason="QA only",
                            status="CONFIRMED"))
    if not db.get(Provider, "qa-lab"):
        db.add(Provider(id="qa-lab", code="QA-LAB", name="QA Laboratory", provider_type="LAB",
                         district="Dhaka", owner_user_id="qa-operator", is_verified=True))
        db.flush()
        db.add(LabTest(id="qa-cbc", provider_id="qa-lab", code="CBC", name="Complete Blood Count",
                        price_bdt=500, sample_type="Blood"))
    db.commit()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ.get("QA_PORT", "8765")))
