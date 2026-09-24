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
    # All 64 district headquarters. With only the twenty largest, every
    # facility in an unlisted district was labelled with its nearest listed
    # neighbour - Madaripur's sadar hospital was coming out as "Barishal".
    "Dhaka": (23.8103, 90.4125),
    "Gazipur": (24.0023, 90.4265),
    "Narayanganj": (23.6226, 90.4996),
    "Narsingdi": (23.9322, 90.7151),
    "Manikganj": (23.8644, 90.0047),
    "Munshiganj": (23.5422, 90.5305),
    "Tangail": (24.2513, 89.9167),
    "Kishoreganj": (24.4449, 90.7766),
    "Faridpur": (23.6070, 89.8429),
    "Gopalganj": (23.0050, 89.8266),
    "Madaripur": (23.1641, 90.1895),
    "Shariatpur": (23.2423, 90.4348),
    "Rajbari": (23.7574, 89.6444),
    "Chattogram": (22.3569, 91.7832),
    "Cox's Bazar": (21.4272, 92.0058),
    "Comilla": (23.4607, 91.1809),
    "Brahmanbaria": (23.9571, 91.1119),
    "Chandpur": (23.2333, 90.6712),
    "Feni": (23.0159, 91.3976),
    "Lakshmipur": (22.9447, 90.8282),
    "Noakhali": (22.8696, 91.0995),
    "Khagrachhari": (23.1193, 91.9847),
    "Rangamati": (22.6533, 92.1735),
    "Bandarban": (22.1953, 92.2184),
    "Khulna": (22.8456, 89.5403),
    "Bagerhat": (22.6516, 89.7859),
    "Chuadanga": (23.6402, 88.8418),
    "Jashore": (23.1697, 89.2137),
    "Jhenaidah": (23.5450, 89.1539),
    "Kushtia": (23.9013, 89.1206),
    "Magura": (23.4855, 89.4198),
    "Meherpur": (23.7622, 88.6318),
    "Narail": (23.1725, 89.5126),
    "Satkhira": (22.7185, 89.0705),
    "Rajshahi": (24.3745, 88.6042),
    "Bogura": (24.8465, 89.3773),
    "Chapainawabganj": (24.5965, 88.2775),
    "Joypurhat": (25.0947, 89.0227),
    "Naogaon": (24.7936, 88.9318),
    "Natore": (24.4206, 89.0003),
    "Pabna": (24.0064, 89.2372),
    "Sirajganj": (24.4534, 89.7007),
    "Sylhet": (24.8949, 91.8687),
    "Habiganj": (24.3745, 91.4155),
    "Moulvibazar": (24.4829, 91.7774),
    "Sunamganj": (25.0658, 91.3950),
    "Barishal": (22.7010, 90.3535),
    "Barguna": (22.0953, 90.1121),
    "Bhola": (22.6859, 90.6482),
    "Jhalokati": (22.6406, 90.1987),
    "Patuakhali": (22.3596, 90.3299),
    "Pirojpur": (22.5841, 89.9720),
    "Rangpur": (25.7439, 89.2752),
    "Dinajpur": (25.6217, 88.6354),
    "Gaibandha": (25.3288, 89.5281),
    "Kurigram": (25.8054, 89.6362),
    "Lalmonirhat": (25.9923, 89.2847),
    "Nilphamari": (25.9317, 88.8560),
    "Panchagarh": (26.3411, 88.5542),
    "Thakurgaon": (26.0337, 88.4616),
    "Mymensingh": (24.7471, 90.4203),
    "Jamalpur": (24.9375, 89.9372),
    "Netrokona": (24.8103, 90.7279),
    "Sherpur": (25.0205, 90.0153),
}

# Capacity by facility size class. The source does not publish bed counts, so
# these are planning assumptions drawn from the DGHS facility tiers, applied by
# what the name says the facility is.
# Bangla name patterns sit beside the English ones because roughly a third
# of the map's facilities carry only a Bangla name, and an English-only
# pattern used to push them to the bottom of every ranking.
TIERS = [
    (r"medical college|teaching hospital|মেডিকেল কলেজ", 500, 40),
    (r"general hospital|sadar hospital|district hospital|জেনারেল হাসপাতাল|সদর হাসপাতাল", 250, 20),
    (r"upazila health complex|health complex|উপজেলা স্বাস্থ্য|স্বাস্থ্য কমপ্লেক্স", 50, 4),
    (r"specialized|specialised|institute", 200, 25),
    (r"maternity|mother|child|মাতৃ|শিশু", 60, 6),
    (r"clinic|diagnostic|ক্লিনিক|ডায়াগনস্টিক", 20, 2),
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
    taken_in_district: dict[tuple[str, str], list] = {}

    with REAL.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    # When the per-district cap bites, keep the facilities a patient is most
    # likely to be sent to: teaching and district hospitals first, then named
    # institutions, and only then the small private clinics that make up the
    # bulk of the map data.
    def _rank(row: dict) -> tuple:
        name = (row.get("name") or "").lower()
        if re.search(r"medical college|teaching hospital|মেডিকেল কলেজ", name):
            tier = 0
        elif re.search(
            r"general hospital|sadar hospital|district hospital"
            r"|জেনারেল হাসপাতাল|সদর হাসপাতাল",
            name,
        ):
            tier = 1
        elif re.search(
            r"upazila health complex|health complex|উপজেলা স্বাস্থ্য|স্বাস্থ্য কমপ্লেক্স",
            name,
        ):
            tier = 2
        elif re.search(
            r"specialized|specialised|institute|hospital|হাসপাতাল",
            name,
        ):
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

        # The map carries the same facility more than once - two nodes for
        # one campus, an English and a Bangla sign, or two upazila complexes
        # that share a generic name. A patient shown "Holy Family" twice
        # reasonably concludes the list is untrustworthy. Skip an entry that
        # repeats a name already taken in the district, or that sits within
        # 250 m of one already taken.
        normalized = re.sub(r"[^\w\u0980-\u09FF]+", "", name.lower())
        if not normalized:
            normalized = name.lower()
        taken = taken_in_district.setdefault((district, kind), [])
        if normalized in {n for n, _ in taken}:
            continue
        if any(_haversine(lat, lon, tlat, tlon) < 0.25
               for _, (tlat, tlon) in taken):
            continue

        per_district[key] = per_district.get(key, 0) + 1
        taken.append((normalized, (lat, lon)))

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
