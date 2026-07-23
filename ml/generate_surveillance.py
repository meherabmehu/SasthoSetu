# -*- coding: utf-8 -*-
"""Generate district-level weekly disease surveillance data (DGHS-style).

Simulates 3 years of weekly case counts for 12 districts x 8 notifiable
conditions with per-disease seasonality (dengue monsoon peak, diarrheal
summer, winter ARI) plus ~25 injected outbreak windows saved as ground truth
— the /v1/population/surveillance anomaly detector demo points at these.

Output:
    data/surveillance/weekly_surveillance.csv
    data/surveillance/injected_outbreaks.csv
"""
from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "surveillance"

DISTRICTS = {  # name: population weight
    "Dhaka": 3.0, "Chattogram": 2.0, "Narayanganj": 1.2, "Gazipur": 1.3,
    "Cumilla": 1.1, "Sylhet": 1.0, "Rajshahi": 1.0, "Khulna": 1.0,
    "Barishal": 0.8, "Rangpur": 0.9, "Mymensingh": 0.9, "Cox's Bazar": 0.7,
}

DISEASES = {  # name: (weekly base per weight-1 district, season)
    "dengue": (18, "monsoon"), "diarrheal_disease": (60, "summer"),
    "ari": (80, "winter"), "typhoid": (14, "summer"),
    "chikungunya": (5, "monsoon"), "hepatitis_a": (7, "flat"),
    "measles": (4, "spring"), "malaria": (3, "monsoon"),
}

SEASON_PEAK_WEEK = {"monsoon": 37, "summer": 22, "winter": 1, "spring": 12,
                    "flat": None}
START, WEEKS = "2023-07-02", 157


def season_factor(kind: str, week_of_year: int) -> float:
    peak = SEASON_PEAK_WEEK[kind]
    if peak is None:
        return 1.0
    d = min(abs(week_of_year - peak), 52 - abs(week_of_year - peak))
    strength = {"monsoon": 2.6, "summer": 1.4, "winter": 1.6, "spring": 1.2}[kind]
    return 1.0 + strength * math.exp(-(d ** 2) / (2 * 5.5 ** 2))


def main(seed: int = 42) -> None:
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)
    weeks = pd.date_range(START, periods=WEEKS, freq="W-SUN")

    outbreaks = []
    combos = [(d, dis) for d in DISTRICTS for dis in DISEASES]
    for d, dis in rng.sample(combos, 25):
        start = rng.randint(10, WEEKS - 8)
        outbreaks.append({"district": d, "disease": dis, "start": start,
                          "length": rng.randint(2, 5),
                          "multiplier": round(rng.uniform(2.5, 6.0), 2)})

    rows = []
    for district, w in DISTRICTS.items():
        for disease, (base, season) in DISEASES.items():
            for i, wk in enumerate(weeks):
                mu = base * w * season_factor(season, int(wk.week))
                for ob in outbreaks:
                    if (ob["district"] == district and ob["disease"] == disease
                            and ob["start"] <= i < ob["start"] + ob["length"]):
                        mu *= ob["multiplier"]
                cases = int(np_rng.poisson(max(mu, 0.5)))
                rows.append({"week_ending": wk.date().isoformat(),
                             "district": district, "disease": disease,
                             "cases": cases})

    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "weekly_surveillance.csv", index=False)
    ob_rows = [{**ob,
                "start_week": weeks[ob["start"]].date().isoformat(),
                "end_week": weeks[min(ob["start"] + ob["length"] - 1,
                                      WEEKS - 1)].date().isoformat()}
               for ob in outbreaks]
    pd.DataFrame(ob_rows).drop(columns=["start", "length"]).to_csv(
        OUT / "injected_outbreaks.csv", index=False)
    print(f"surveillance rows={len(rows)}, injected outbreaks={len(outbreaks)} -> {OUT}")


if __name__ == "__main__":
    main()
