# -*- coding: utf-8 -*-
"""Generate synthetic hospital bed-utilization logs for the surge model.

Simulates 2 years of daily general-ward + ICU occupancy for 5 Dhaka demo
hospitals with realistic structure: baseline load, weekly admission rhythm,
dengue season (Jul-Oct, peaking Sep), winter respiratory season (Dec-Jan),
random surge events, and noise. Ground-truth surge events are also written
so forecast demos can point at known spikes.

Output:
    data/surge/bed_utilization.csv
    data/surge/surge_events.csv
"""
from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "surge"

HOSPITALS = [
    {"hospital_id": "H001", "name": "Dhaka Medical College Hospital",
     "wards": {"general": 320, "icu": 40}, "base": 0.86},
    {"hospital_id": "H002", "name": "Square Hospital",
     "wards": {"general": 220, "icu": 30}, "base": 0.74},
    {"hospital_id": "H003", "name": "Ibn Sina Hospital Dhanmondi",
     "wards": {"general": 150, "icu": 15}, "base": 0.71},
    {"hospital_id": "H004", "name": "Labaid Specialized Hospital",
     "wards": {"general": 180, "icu": 20}, "base": 0.72},
    {"hospital_id": "H005", "name": "United Hospital",
     "wards": {"general": 160, "icu": 22}, "base": 0.69},
]

START, END = "2024-08-01", "2026-07-21"


def seasonal(day: pd.Timestamp) -> float:
    doy = day.dayofyear
    dengue = 0.11 * math.exp(-((doy - 255) ** 2) / (2 * 38 ** 2))  # peak ~mid-Sep
    winter = 0.06 * math.exp(-((min(doy, 366 - doy)) ** 2) / (2 * 25 ** 2))
    weekly = 0.02 * math.sin(2 * math.pi * day.dayofweek / 7)
    return dengue + winter + weekly


def main(seed: int = 42) -> None:
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)
    dates = pd.date_range(START, END, freq="D")

    # random surge events: (hospital, ward, start_idx, length, magnitude)
    events = []
    for h in HOSPITALS:
        for ward in h["wards"]:
            for _ in range(rng.randint(3, 5)):
                events.append({
                    "hospital_id": h["hospital_id"], "ward_type": ward,
                    "start": rng.randint(30, len(dates) - 15),
                    "length": rng.randint(3, 8),
                    "magnitude": rng.uniform(0.08, 0.20),
                })

    rows = []
    for h in HOSPITALS:
        for ward, cap in h["wards"].items():
            icu_bump = 0.04 if ward == "icu" else 0.0
            for i, day in enumerate(dates):
                rate = h["base"] + icu_bump + seasonal(day)
                for ev in events:
                    if (ev["hospital_id"] == h["hospital_id"]
                            and ev["ward_type"] == ward
                            and ev["start"] <= i < ev["start"] + ev["length"]):
                        rate += ev["magnitude"]
                rate += np_rng.normal(0, 0.025)
                rate = float(np.clip(rate, 0.35, 1.0))
                occupied = int(round(rate * cap))
                rows.append({
                    "date": day.date().isoformat(),
                    "hospital_id": h["hospital_id"],
                    "hospital_name": h["name"],
                    "ward_type": ward,
                    "capacity": cap,
                    "occupied": occupied,
                    "available": cap - occupied,
                    "occupancy_rate": round(occupied / cap, 4),
                })

    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "bed_utilization.csv", index=False)
    ev_rows = [{**ev, "start_date": dates[ev["start"]].date().isoformat(),
                "end_date": dates[min(ev["start"] + ev["length"] - 1,
                                      len(dates) - 1)].date().isoformat()}
               for ev in events]
    pd.DataFrame(ev_rows).drop(columns=["start", "length"]).to_csv(
        OUT / "surge_events.csv", index=False)
    print(f"bed rows={len(rows)}, surge events={len(events)} -> {OUT}")


if __name__ == "__main__":
    main()
