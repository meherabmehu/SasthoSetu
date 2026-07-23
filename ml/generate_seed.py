# -*- coding: utf-8 -*-
"""Generate demo seed data: 5 Dhaka hospitals + 50 doctors.

Per the hackathon sprint plan (section 8.1, Day 2): "Mock data seeded for
5 hospitals (Dhaka) + 50 doctors." Deterministic, JSON output consumed by
the doctor-matching service and DB seeding script.

Output: data/seed/hospitals.json, data/seed/doctors.json
"""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "seed"

HOSPITALS = [
    {"hospital_id": "H001", "name": "Dhaka Medical College Hospital",
     "area": "Shahbag", "lat": 23.7258, "lng": 90.3973,
     "emergency": True, "icu_beds": 40, "general_beds": 320},
    {"hospital_id": "H002", "name": "Square Hospital",
     "area": "Panthapath", "lat": 23.7526, "lng": 90.3810,
     "emergency": True, "icu_beds": 30, "general_beds": 220},
    {"hospital_id": "H003", "name": "Ibn Sina Hospital Dhanmondi",
     "area": "Dhanmondi", "lat": 23.7461, "lng": 90.3742,
     "emergency": True, "icu_beds": 15, "general_beds": 150},
    {"hospital_id": "H004", "name": "Labaid Specialized Hospital",
     "area": "Dhanmondi", "lat": 23.7398, "lng": 90.3854,
     "emergency": True, "icu_beds": 20, "general_beds": 180},
    {"hospital_id": "H005", "name": "United Hospital",
     "area": "Gulshan", "lat": 23.8041, "lng": 90.4152,
     "emergency": True, "icu_beds": 22, "general_beds": 160},
]

FIRST = ["Rahim", "Karim", "Fatema", "Ayesha", "Mahmud", "Nusrat", "Tanvir",
         "Sabrina", "Imran", "Farhana", "Shakil", "Sharmin", "Rafiq",
         "Taslima", "Habib", "Nasrin", "Jahid", "Sultana", "Arif", "Rumana",
         "Kamal", "Shirin", "Selim", "Papia", "Monir"]
LAST = ["Ahmed", "Hossain", "Rahman", "Islam", "Chowdhury", "Khan", "Akter",
        "Uddin", "Begum", "Talukder", "Sarkar", "Mia", "Bhuiyan", "Karim"]

SPECIALTY_POOL = (
    ["General Medicine"] * 9 + ["Cardiology"] * 5 + ["Pulmonology"] * 4
    + ["Gastroenterology"] * 4 + ["Neurology"] * 4 + ["Orthopedics"] * 4
    + ["Gynaecology & Obstetrics"] * 4 + ["Paediatrics"] * 3
    + ["Dermatology"] * 3 + ["ENT"] * 3 + ["Urology"] * 2
    + ["Ophthalmology"] * 2 + ["Psychiatry"] * 2 + ["Endocrinology"] * 2
    + ["Nephrology"] * 2 + ["Dentistry"] * 2 + ["Emergency"] * 1
)  # 56 slots -> first 50 used after shuffle

SLOT_PATTERNS = [
    ["09:00", "10:00", "11:00", "17:00", "18:00"],
    ["10:00", "11:00", "18:00", "19:00", "20:00"],
    ["08:00", "09:00", "16:00", "17:00"],
    ["11:00", "12:00", "19:00", "20:00", "21:00"],
]


def main(seed: int = 42) -> None:
    rng = random.Random(seed)
    pool = SPECIALTY_POOL[:]
    rng.shuffle(pool)

    doctors = []
    for i in range(50):
        h = rng.choice(HOSPITALS)
        sex = rng.choice(["M", "F"])
        title = "Dr." 
        name = f"{title} {rng.choice(FIRST)} {rng.choice(LAST)}"
        doctors.append({
            "doctor_id": f"D{i + 1:03d}",
            "name": name,
            "sex": sex,
            "specialty": pool[i],
            "bmdc_reg_no": f"A-{rng.randint(30000, 99999)}",
            "bmdc_verified": True,
            "hospital_id": h["hospital_id"],
            "hospital_name": h["name"],
            "lat": round(h["lat"] + rng.uniform(-0.004, 0.004), 6),
            "lng": round(h["lng"] + rng.uniform(-0.004, 0.004), 6),
            "consult_fee_bdt": rng.choice([500, 600, 700, 800, 1000, 1200, 1500]),
            "teleconsult_enabled": rng.random() < 0.85,
            "languages": ["bn", "en"] if rng.random() < 0.8 else ["bn"],
            "rating": round(rng.uniform(3.6, 5.0), 1),
            "experience_years": rng.randint(3, 30),
            "available_slots": rng.choice(SLOT_PATTERNS),
        })

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "hospitals.json").write_text(json.dumps(HOSPITALS, indent=2))
    (OUT / "doctors.json").write_text(json.dumps(doctors, indent=2))
    specs = sorted({d["specialty"] for d in doctors})
    print(f"hospitals=5 doctors=50 specialties_covered={len(specs)} -> {OUT}")


if __name__ == "__main__":
    main()
