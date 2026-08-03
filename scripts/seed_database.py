# -*- coding: utf-8 -*-
"""Seed the database with reference facilities, doctors and demo accounts.

Idempotent: existing rows are updated in place rather than duplicated, so the
script is safe to re-run against a live environment.

Run ``alembic upgrade head`` first.

    python scripts/seed_database.py
"""
from __future__ import annotations

import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.drug_safety import normalize_drug  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.doctor import Doctor  # noqa: E402
from app.models.doctor_availability import DoctorAvailability  # noqa: E402
from app.models.hospital import Hospital, Ward  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.models.provider import (  # noqa: E402
    LabTest,
    PharmacyStock,
    Provider,
)
from app.models.user import User  # noqa: E402

SEED_DIR = ROOT / "data" / "seed"

# Ward mix applied to each seeded hospital, as a share of its bed count.
WARD_TEMPLATE = [
    ("general", "General Ward", 0.70),
    ("icu", "Intensive Care Unit", 0.10),
    ("emergency", "Emergency Department", 0.08),
    ("hdu", "High Dependency Unit", 0.05),
    ("maternity", "Maternity Ward", 0.04),
    ("paediatric", "Paediatric Ward", 0.03),
]

DEMO_ACCOUNTS = [
    {
        "full_name": "SasthoSetu Administrator",
        "email": "admin@sasthosetu.gov.bd",
        "phone": "01700000001",
        "password": "Admin@12345",
        "role": "ADMIN",
    },
    {
        "full_name": "Rina Begum",
        "email": "patient@sasthosetu.gov.bd",
        "phone": "01700000002",
        "password": "Patient@12345",
        "role": "PATIENT",
    },
    {
        "full_name": "Dr. Tanvir Ahmed",
        "email": "doctor@sasthosetu.gov.bd",
        "phone": "01700000003",
        "password": "Doctor@12345",
        "role": "DOCTOR",
    },
]


def _upsert_user(db, spec):
    user = db.query(User).filter(User.email == spec["email"]).first()
    if user:
        user.full_name = spec["full_name"]
        user.role = spec["role"]
        user.is_active = True
        user.is_verified = True
        return user, False

    user = User(
        full_name=spec["full_name"],
        email=spec["email"],
        phone=spec["phone"],
        password_hash=hash_password(spec["password"]),
        role=spec["role"],
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    return user, True


def seed_hospitals(db) -> int:
    path = SEED_DIR / "hospitals.json"
    if not path.exists():
        print(f"  skipped: {path} missing (run ml/generate_seed.py)")
        return 0

    records = json.loads(path.read_text(encoding="utf-8"))
    created = 0

    for record in records:
        hospital = (
            db.query(Hospital).filter(Hospital.code == record["hospital_id"]).first()
        )
        if not hospital:
            hospital = Hospital(code=record["hospital_id"])
            db.add(hospital)
            created += 1

        hospital.name = record["name"]
        hospital.district = record.get("district", "Dhaka")
        hospital.area = record.get("area")
        hospital.latitude = record.get("lat")
        hospital.longitude = record.get("lng")
        hospital.has_emergency = bool(record.get("emergency", True))
        hospital.is_active = True
        db.flush()

        total_beds = int(record.get("general_beds", 0)) + int(
            record.get("icu_beds", 0)
        )

        for ward_type, ward_name, share in WARD_TEMPLATE:
            if ward_type == "icu":
                capacity = int(record.get("icu_beds", 0))
            else:
                capacity = max(1, int(total_beds * share))

            ward = (
                db.query(Ward)
                .filter(Ward.hospital_id == hospital.id, Ward.ward_type == ward_type)
                .first()
            )
            if not ward:
                ward = Ward(
                    hospital_id=hospital.id,
                    ward_type=ward_type,
                    name=ward_name,
                    total_beds=capacity,
                    # Start near a realistic occupancy rather than empty.
                    occupied_beds=int(capacity * 0.78),
                )
                db.add(ward)
            else:
                ward.total_beds = capacity
                ward.name = ward_name

    return created


def seed_doctors(db) -> int:
    path = SEED_DIR / "doctors.json"
    if not path.exists():
        print(f"  skipped: {path} missing (run ml/generate_seed.py)")
        return 0

    records = json.loads(path.read_text(encoding="utf-8"))
    created = 0

    # Availability is published for the coming week so the booking flow has
    # real slots to offer immediately after seeding.
    upcoming = [
        (date.today() + timedelta(days=offset)).isoformat()
        for offset in range(1, 8)
    ]

    for index, record in enumerate(records):
        email = f"{record['doctor_id'].lower()}@doctors.sasthosetu.gov.bd"
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                full_name=record["name"],
                email=email,
                phone=f"017{10000000 + index:08d}"[:11],
                password_hash=hash_password("Doctor@12345"),
                role="DOCTOR",
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            db.flush()

        doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
        if not doctor:
            doctor = Doctor(
                user_id=user.id,
                bmdc_number=record["bmdc_reg_no"],
                specialization=record["specialty"],
                experience_years=int(record.get("experience_years", 5)),
                consultation_fee=float(record.get("consult_fee_bdt", 800)),
                hospital_name=record.get("hospital_name", "SasthoSetu Network"),
                bio=(
                    f"{record['specialty']} at {record.get('hospital_name', '')}. "
                    f"{record.get('experience_years', 0)} years of experience."
                ).strip(),
                verification_status=bool(record.get("bmdc_verified", True)),
            )
            db.add(doctor)
            db.flush()
            created += 1
        else:
            doctor.specialization = record["specialty"]
            doctor.consultation_fee = float(record.get("consult_fee_bdt", 800))
            doctor.verification_status = bool(record.get("bmdc_verified", True))

        for date_text in upcoming:
            for slot in record.get("available_slots", []):
                exists = (
                    db.query(DoctorAvailability)
                    .filter(
                        DoctorAvailability.doctor_id == doctor.id,
                        DoctorAvailability.available_date == date_text,
                        DoctorAvailability.start_time == slot,
                    )
                    .first()
                )
                if exists:
                    continue

                hour, minute = slot.split(":")
                end_time = f"{(int(hour) + 1) % 24:02d}:{minute}"
                db.add(
                    DoctorAvailability(
                        doctor_id=doctor.id,
                        available_date=date_text,
                        start_time=slot,
                        end_time=end_time,
                        is_booked=False,
                    )
                )

    return created


def seed_demo_accounts(db) -> int:
    created = 0
    for spec in DEMO_ACCOUNTS:
        user, is_new = _upsert_user(db, spec)
        created += int(is_new)

        if spec["role"] == "PATIENT":
            patient = db.query(Patient).filter(Patient.user_id == user.id).first()
            if not patient:
                db.add(
                    Patient(
                        user_id=user.id,
                        date_of_birth=date(1992, 4, 17),
                        gender="FEMALE",
                        blood_group="B+",
                        height_cm=155.0,
                        weight_kg=58.0,
                        emergency_contact="01700000004",
                        address="Tangail Sadar, Tangail",
                    )
                )

        if spec["role"] == "DOCTOR":
            doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
            if not doctor:
                db.add(
                    Doctor(
                        user_id=user.id,
                        bmdc_number="BMDC-DEMO-0001",
                        specialization="General Medicine",
                        experience_years=8,
                        consultation_fee=700.0,
                        hospital_name="Dhaka Medical College Hospital",
                        bio="Demo account for the SasthoSetu doctor portal.",
                        verification_status=True,
                    )
                )

    return created


# Pharmacies and labs across the districts the platform launches in. Real
# chains, so the directory reads plausibly to a Bangladeshi user.
PHARMACIES = [
    ("PH001", "Lazz Pharma", "Dhaka", "Dhanmondi", "01711000001"),
    ("PH002", "Tamanna Pharmacy", "Dhaka", "Mirpur", "01711000002"),
    ("PH003", "Wellbeing Pharmacy", "Dhaka", "Gulshan", "01711000003"),
    ("PH004", "Shastho Pharma", "Dhaka", "Uttara", "01711000004"),
    ("PH005", "Al-Madina Pharmacy", "Chattogram", "Agrabad", "01711000005"),
    ("PH006", "Sylhet Medicine Corner", "Sylhet", "Zindabazar", "01711000006"),
]

LABS = [
    ("LAB001", "Popular Diagnostic Centre", "Dhaka", "Dhanmondi", "01711000101"),
    ("LAB002", "Ibn Sina Diagnostic", "Dhaka", "Mirpur", "01711000102"),
    ("LAB003", "Medinova Medical Services", "Dhaka", "Malibagh", "01711000103"),
    ("LAB004", "Chevron Clinical Laboratory", "Chattogram", "Panchlaish",
     "01711000104"),
]

# Common tests with realistic Bangladeshi private-lab pricing in BDT.
LAB_CATALOGUE = [
    ("CBC", "Complete Blood Count", "blood", 400, 24),
    ("NS1", "Dengue NS1 Antigen", "blood", 800, 24),
    ("DENGUE-IGG", "Dengue IgG/IgM", "blood", 1200, 24),
    ("WIDAL", "Widal Test (typhoid)", "blood", 500, 24),
    ("FBS", "Fasting Blood Sugar", "blood", 200, 6),
    ("HBA1C", "HbA1c", "blood", 1200, 24),
    ("LFT", "Liver Function Test", "blood", 1500, 24),
    ("KFT", "Kidney Function Test", "blood", 1400, 24),
    ("URINE-RE", "Urine Routine Examination", "urine", 300, 12),
    ("CXR", "Chest X-Ray", "imaging", 600, 4),
    ("ECG", "Electrocardiogram", "none", 400, 2),
    ("SPUTUM-AFB", "Sputum for AFB (TB)", "sputum", 300, 48),
    ("LIPID", "Lipid Profile", "blood", 1000, 24),
    ("TSH", "Thyroid Stimulating Hormone", "blood", 900, 24),
]

# Stocked medicines, chosen to cover the conditions triage actually surfaces:
# fever, infection, gastric, cardiac, diabetes and asthma.
STOCK_ITEMS = [
    ("Napa 500", "500mg", 1.20),
    ("Ace 500", "500mg", 1.50),
    ("Napa Extra", "500mg", 2.00),
    ("Seclo 20", "20mg", 5.00),
    ("Maxpro 20", "20mg", 7.00),
    ("Pantonix 20", "20mg", 6.00),
    ("Alatrol 10", "10mg", 2.50),
    ("Fexo 120", "120mg", 8.00),
    ("Monas 10", "10mg", 15.00),
    ("Zimax 500", "500mg", 35.00),
    ("Moxacil 500", "500mg", 8.00),
    ("Ciprocin 500", "500mg", 12.00),
    ("Flagyl 400", "400mg", 3.50),
    ("Doxicap 100", "100mg", 4.00),
    ("Comet 500", "500mg", 3.00),
    ("Amaryl 2", "2mg", 12.00),
    ("Atova 10", "10mg", 12.00),
    ("Ecosprin 75", "75mg", 1.50),
    ("Amdocal 5", "5mg", 5.00),
    ("Losartan 50", "50mg", 7.00),
    ("Indever 10", "10mg", 1.50),
    ("Thyrox 50", "50mcg", 4.50),
    ("Ventolin", "100mcg", 320.00),
    ("Deltasone 5", "5mg", 2.00),
    ("Emistat 4", "4mg", 6.00),
    ("Omidon 10", "10mg", 2.00),
    ("Sedil 5", "5mg", 3.00),
    ("Tufnil 200", "200mg", 9.00),
]


def _upsert_provider(db, code, name, provider_type, district, area, phone):
    provider = db.query(Provider).filter(Provider.code == code).first()
    created = provider is None
    if created:
        provider = Provider(code=code)
        db.add(provider)

    provider.name = name
    provider.provider_type = provider_type
    provider.district = district
    provider.area = area
    provider.phone = phone
    # Verified, so ordering and stock search work immediately after seeding.
    provider.is_verified = True
    provider.is_active = True
    db.flush()
    return provider, created


def seed_pharmacies(db) -> int:
    """Pharmacies with stock, so medicine search returns something."""
    created = 0
    rng = random.Random(42)

    for index, (code, name, district, area, phone) in enumerate(PHARMACIES):
        provider, is_new = _upsert_provider(
            db, code, name, "PHARMACY", district, area, phone
        )
        created += int(is_new)

        # Stock is unique per (generic, strength), and several catalogue
        # entries share a generic - Napa and Ace are both paracetamol 500mg.
        # Track what this branch already carries so the first brand wins
        # rather than the insert failing on the constraint.
        carried: set[tuple[str, str]] = set()

        # Each pharmacy carries most but not all of the catalogue, so a search
        # genuinely distinguishes between branches rather than returning an
        # identical list every time.
        for item_index, (brand, strength, price) in enumerate(STOCK_ITEMS):
            if (item_index + index) % 7 == 0:
                continue

            generic = normalize_drug(brand)
            key = (generic, strength)
            if key in carried:
                continue
            carried.add(key)

            existing = (
                db.query(PharmacyStock)
                .filter(
                    PharmacyStock.provider_id == provider.id,
                    PharmacyStock.generic_name == generic,
                    PharmacyStock.strength == strength,
                )
                .first()
            )
            if existing:
                continue

            db.add(
                PharmacyStock(
                    provider_id=provider.id,
                    brand_name=brand,
                    generic_name=generic,
                    strength=strength,
                    # Small per-branch price variation, as in the real market.
                    unit_price_bdt=round(price * rng.uniform(0.95, 1.15), 2),
                    quantity_available=rng.randint(20, 500),
                )
            )

    return created


def seed_labs(db) -> int:
    """Diagnostic centres with a test catalogue."""
    created = 0
    rng = random.Random(7)

    for index, (code, name, district, area, phone) in enumerate(LABS):
        provider, is_new = _upsert_provider(
            db, code, name, "LAB", district, area, phone
        )
        created += int(is_new)

        for test_index, (test_code, test_name, sample, price, hours) in enumerate(
            LAB_CATALOGUE
        ):
            if (test_index + index) % 8 == 0:
                continue

            existing = (
                db.query(LabTest)
                .filter(
                    LabTest.provider_id == provider.id,
                    LabTest.code == test_code,
                )
                .first()
            )
            if existing:
                continue

            db.add(
                LabTest(
                    provider_id=provider.id,
                    code=test_code,
                    name=test_name,
                    sample_type=sample,
                    price_bdt=round(price * rng.uniform(0.9, 1.2)),
                    turnaround_hours=hours,
                )
            )

    return created


def main() -> None:
    db = SessionLocal()
    try:
        print("Seeding hospitals and wards...")
        hospitals = seed_hospitals(db)
        db.commit()

        print("Seeding doctors...")
        doctors = seed_doctors(db)
        db.commit()

        print("Seeding pharmacies and stock...")
        pharmacies = seed_pharmacies(db)
        db.commit()

        print("Seeding diagnostic labs...")
        labs = seed_labs(db)
        db.commit()

        print("Seeding demo accounts...")
        accounts = seed_demo_accounts(db)
        db.commit()

        print(
            f"\nDone. new hospitals={hospitals} new doctors={doctors} "
            f"new pharmacies={pharmacies} new labs={labs} "
            f"new accounts={accounts}"
        )
        print("\nDemo credentials:")
        for spec in DEMO_ACCOUNTS:
            print(f"  {spec['role']:8} {spec['email']}  {spec['password']}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
