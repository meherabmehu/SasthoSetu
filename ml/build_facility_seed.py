# -*- coding: utf-8 -*-
"""Build the hospital, pharmacy and lab seed from real facility data.

The platform shipped with five hand-written hospitals. Proximity ranking is
only as good as the directory behind it, and five facilities cannot serve a
country: a patient in Rangpur was being offered a hospital in Dhaka because
nothing nearer existed in the database.

OpenStreetMap's Bangladesh health facilities, published through HDX under ODbL,
carry real names and coordinates for thousands of hospitals, pharmacies and
laboratories. This converts them into the seed format the loader already reads.

What is real and what is not:

* name, type and coordinates come from the source and are used as they are
* district is derived from the coordinates against division centroids, because
  the source does not carry an administrative district field
* **bed counts are not in the source** — only 2 of 1,556 hospitals record them.
  Capacity is therefore assigned by facility size class, and is explicitly an
  assumption, not an observation. Live occupancy has to come from each
  hospital's own system.

    python ml/build_facility_seed.py
    python ml/build_facility_seed.py --limit-per-district 40

Output: data/seed/hospitals.json, data/seed/pharmacies.json,
        data/seed/laboratories.json
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "data" / "real" / "bd_health_facilities.csv"
SEED = ROOT / "data" / "seed"

# District centroids for the districts the platform launches in, plus the
# divisional headquarters so that a facility anywhere in the country lands
# somewhere sensible. Coordinates are the district town centres.
DISTRICTS = {
    "Dhaka": (23.8103, 90.4125),
    "Chattogram": (22.3569, 91.7832),
    "Khulna": (22.8456, 89.5403),
    "Rajshahi": (24.3745, 88.6042),
    "Sylhet": (24.8949, 91.8687),
    "Barishal": (22.7010, 90.3535),
    "Rangpur": (25.7439, 89.2752),
    "Mymensingh": (24.7471, 90.4203),
    "Comilla": (23.4607, 91.1809),
    "Gazipur": (23.9999, 90.4203),
    "Narayanganj": (23.6238, 90.5000),
    "Bogura": (24.8465, 89.3773),
    "Jashore": (23.1697, 89.2137),
    "Cox's Bazar": (21.4272, 92.0058),
    "Dinajpur": (25.6217, 88.6354),
    "Faridpur": (23.6070, 89.8429),
    "Kushtia": (23.9013, 89.1206),
    "Noakhali": (22.8696, 91.0995),
    "Pabna": (24.0064, 89.2372),
    "Tangail": (24.2513, 89.9167),
}

# Capacity by facility size class. The source does not publish bed counts, so
# these are planning assumptions drawn from the DGHS facility tiers, applied by
# what the name says the facility is.
TIERS = [
    (r"medical college|teaching hospital", 500, 40),
    (r"general hospital|sadar hospital|district hospital", 250, 20),
    (r"upazila health complex|health complex", 50, 4),
    (r"specialized|specialised|institute", 200, 25),
    (r"maternity|mother|child", 60, 6),
    (r"clinic|diagnostic", 20, 2),
]
DEFAULT_BEDS = (80, 8)


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def _district_for(lat: float, lon: float) -> str:
    return min(
        DISTRICTS,
        key=lambda name: _haversine(lat, lon, *DISTRICTS[name]),
    )


def _capacity(name: str) -> tuple[int, int]:
    lowered = name.lower()
    for pattern, general, icu in TIERS:
        if re.search(pattern, lowered):
            return general, icu
    return DEFAULT_BEDS


def _has_emergency(name: str, flag: str) -> bool:
    if flag.strip().lower() in {"yes", "true", "1"}:
        return True
    lowered = name.lower()
    return bool(re.search(
        r"medical college|general hospital|sadar|district hospital|"
        r"health complex|teaching", lowered))


def _clean_name(name: str) -> str:
    """Trim the address tail that map entries often append to the name.

    OpenStreetMap names frequently read "X Hospital, Road 4, Dhaka". Only the
    institution's own name belongs in a directory listing.
    """
    text = " ".join(name.split())
    for separator in (", Government hospital", ", Govt hospital"):
        text = text.split(separator)[0]
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) > 1:
        kept = [parts[0]]
        for part in parts[1:]:
            # Keep a qualifier that is part of the name, drop street or area.
            if re.search(r"hospital|clinic|centre|center|unit|institute",
                         part, re.I) and len(kept) < 2:
                kept.append(part)
            else:
                break
        text = ", ".join(kept)
    return text[:110]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit-per-district",
        type=int,
        default=30,
        help="cap facilities kept per district per type (default: 30)",
    )
    args = parser.parse_args()

    if not REAL.exists():
        print(f"{REAL.relative_to(ROOT)} is missing — "
              "run ml/fetch_real_data.py first")
        raise SystemExit(1)

    buckets: dict[str, list[dict]] = {
        "hospital": [], "pharmacy": [], "laboratory": [],
    }
    per_district: dict[tuple[str, str], int] = {}

    with REAL.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    # When the per-district cap bites, keep the facilities a patient is most
    # likely to be sent to: teaching and district hospitals first, then named
    # institutions, and only then the small private clinics that make up the
    # bulk of the map data.
    def _rank(row: dict) -> tuple:
        name = (row.get("name") or "").lower()
        if re.search(r"medical college|teaching hospital", name):
            tier = 0
        elif re.search(r"general hospital|sadar hospital|district hospital",
                       name):
            tier = 1
        elif re.search(r"upazila health complex|health complex", name):
            tier = 2
        elif re.search(r"specialized|specialised|institute|hospital", name):
            tier = 3
        else:
            tier = 4
        return (tier, -len(name))

    rows.sort(key=_rank)

    for row in rows:
        kind = row["kind"]
        if kind not in buckets:
            continue
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
        except (TypeError, ValueError):
            continue
        if not (20.0 <= lat <= 27.0 and 88.0 <= lon <= 93.0):
            continue

        name = _clean_name(row["name"])
        if len(name) < 4:
            continue

        district = _district_for(lat, lon)
        key = (district, kind)
        if per_district.get(key, 0) >= args.limit_per_district:
            continue
        per_district[key] = per_district.get(key, 0) + 1

        buckets[kind].append({
            "name": name,
            "district": district,
            "lat": round(lat, 6),
            "lng": round(lon, 6),
            "raw_beds": row.get("beds", ""),
            "raw_emergency": row.get("emergency", ""),
        })

    SEED.mkdir(parents=True, exist_ok=True)

    hospitals = []
    for index, item in enumerate(buckets["hospital"], start=1):
        general, icu = _capacity(item["name"])
        recorded = item["raw_beds"].strip()
        if recorded.isdigit() and int(recorded) > 0:
            # Where the source does record beds, prefer the observation.
            general = int(recorded)
            icu = max(2, general // 10)
        hospitals.append({
            "hospital_id": f"H{index:04d}",
            "name": item["name"],
            "district": item["district"],
            "area": item["district"],
            "lat": item["lat"],
            "lng": item["lng"],
            "emergency": _has_emergency(item["name"], item["raw_emergency"]),
            "icu_beds": icu,
            "general_beds": general,
        })

    (SEED / "hospitals.json").write_text(
        json.dumps(hospitals, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"hospitals    : {len(hospitals):,} "
          f"across {len({h['district'] for h in hospitals})} districts")

    for kind, filename in (("pharmacy", "pharmacies.json"),
                           ("laboratory", "laboratories.json")):
        records = [
            {
                "code": f"{kind[:4].upper()}{index:04d}",
                "name": item["name"],
                "district": item["district"],
                "area": item["district"],
                "lat": item["lat"],
                "lng": item["lng"],
            }
            for index, item in enumerate(buckets[kind], start=1)
        ]
        (SEED / filename).write_text(
            json.dumps(records, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"{kind:13}: {len(records):,}")


if __name__ == "__main__":
    main()
