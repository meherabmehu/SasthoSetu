"""Build the checked-in historical Bangladesh dengue estimates table.

The source archive is a CC BY 4.0 empirical dataset.  Its `effected` fields
are fractional estimates, so this script deliberately calls them estimates;
they must not be represented as an official or live DGHS case feed.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "real" / "_cache" / "bd_daily_dengue_v1.zip"
OUTPUT = ROOT / "data" / "real" / "bd_dengue_daily_2022_2024.csv"
PROVENANCE = ROOT / "data" / "real" / "bd_dengue_daily_2022_2024.provenance.json"


def _division_from_member(name: str) -> str:
    aliases = {
        "barisal": "Barishal", "chittagong": "Chattogram",
        "khulna": "Khulna", "dhaka": "Dhaka", "mymensingh": "Mymensingh",
        "rajshahi": "Rajshahi", "rangpur": "Rangpur", "sylhet": "Sylhet",
    }
    return aliases[Path(name).stem.lower()]


def build() -> dict:
    if not CACHE.exists():
        raise FileNotFoundError(f"Missing source archive: {CACHE}")
    rows: list[dict[str, str]] = []
    with zipfile.ZipFile(CACHE) as archive:
        for member in archive.namelist():
            if not member.lower().endswith(".csv"):
                continue
            division = _division_from_member(member)
            text = io.TextIOWrapper(archive.open(member), encoding="utf-8-sig")
            for source in csv.DictReader(text):
                affected_key = next(key for key in source if key.lower().startswith("effected"))
                rows.append({
                    "date": source["Date"],
                    "division": division,
                    "estimated_cases": f"{float(source[affected_key]):.6f}",
                    "rainfall": source.get("Rainfall", ""),
                    "humidity": source.get("Humidity", ""),
                    "temperature": source.get("Temparature", ""),
                    "sunshine": source.get("Sunshine", ""),
                    "windspeed": source.get("Windspeed", ""),
                })
    rows.sort(key=lambda row: (row["division"], row["date"]))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    digest = hashlib.file_digest(CACHE.open("rb"), "sha256").hexdigest()
    payload = {
        "source": "https://data.mendeley.com/datasets/z5mvwrfgsz/1",
        "download": "https://data.mendeley.com/public-api/zip/z5mvwrfgsz/download/1",
        "licence": "CC BY 4.0",
        "source_archive_sha256": digest,
        "rows": len(rows),
        "coverage": {"start": "2022-01-01", "end": "2024-12-31"},
        "measure": "estimated daily dengue affected people; fractional values retained",
        "not_live": True,
        "not_official_case_feed": True,
    }
    PROVENANCE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
