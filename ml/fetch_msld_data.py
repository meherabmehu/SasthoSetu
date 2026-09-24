# -*- coding: utf-8 -*-
"""Fetch the Mpox Skin Lesion Dataset v2.0 (MSLD v2.0).

Five-fold cross-validation layout over 755 original photographs from 541
patients, each labelled by class in its filename prefix:

    MKP  monkeypox      CHP  chickenpox     MSL  measles
    CWP  cowpox         HFMD hand-foot-mouth disease
    HEALTHY

Only one fold is extracted: the same photograph appears in all five fold
directories (that is what five-fold cross-validation means), so taking them
all would copy every image five times and leak it across any split.

The photographs are dermatologist-verified, which is why this sits beside
the MSID screen rather than replacing it: same idea, stronger review, and
two classes - cowpox and hand-foot-mouth disease - that no other dataset we
serve carries at all.

Hosted on Google Drive by the authors (license badge: CC BY 4.0); the
download needs a Drive session, so the archive is fetched with gdown rather
than plain urllib. If gdown is unavailable, see SOURCES.md for the manual
link.

Output: data/real/imaging/msld/ (images, gitignored) and
data/real/imaging/msld_labels.csv (committed).

    python ml/fetch_msld_data.py
"""
from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGING = ROOT / "data" / "real" / "imaging"
CACHE = ROOT / "data" / "real" / "_cache"
OUT_DIR = IMAGING / "msld"
LABELS = IMAGING / "msld_labels.csv"

DRIVE_URL = (
    "https://drive.google.com/drive/folders/"
    "1_bGmbDQNgJViQenjZ4QUhhzpdiubga48"
)

CLASSES = {
    "MKP": {"label_id": 0, "code": "monkeypox",
            "bn": "মাংকিপক্স (এমপক্স) সন্দেহ", "urgency": "see_doctor_soon"},
    "CWP": {"label_id": 1, "code": "cowpox",
            "bn": "কাউপক্স সন্দেহ", "urgency": "see_doctor_soon"},
    "HFMD": {"label_id": 2, "code": "hfmd",
             "bn": "হাত-পা-মুখ রোগ", "urgency": "get_it_checked"},
    "MSL": {"label_id": 3, "code": "measles",
            "bn": "হাম", "urgency": "get_it_checked"},
    "CHP": {"label_id": 4, "code": "chickenpox",
            "bn": "জলবসন্ত (চিকেনপক্স)", "urgency": "get_it_checked"},
    "HEALTHY": {"label_id": 5, "code": "healthy",
                "bn": "স্বাভাবিক ত্বক", "urgency": "watch_it"},
}


def _fetch_archive() -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / "msld_original.zip"
    if cached.exists() and cached.stat().st_size > 40_000_000:
        return cached

    print("  downloading MSLD v2.0 originals from Google Drive (43 MB)...")
    # gdown carries the Drive session dance that urllib cannot.
    subprocess.run(
        [sys.executable, "-m", "gdown", "--folder", DRIVE_URL,
         "-O", str(CACHE / "msld_dl"), "-q"],
        check=True,
    )
    downloaded = CACHE / "msld_dl" / "Original Images.zip"
    downloaded.rename(cached)
    return cached


def main() -> None:
    print("=== MSLD v2.0 viral rash photographs (CC BY 4.0)")

    archive = _fetch_archive()
    source = zipfile.ZipFile(archive)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[str] = ["file,label_id,code,condition,condition_bn,urgency\n"]
    kept = 0
    seen: set[str] = set()

    for name in source.namelist():
        if "fold1" not in name:
            # One fold only - every image lives in all five.
            continue
        if not name.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        stem = Path(name).stem
        prefix = stem.split("_")[0]
        spec = CLASSES.get(prefix)
        if spec is None or stem in seen:
            continue
        seen.add(stem)
        blob = source.read(name)
        if not blob:
            continue
        filename = f"msld_{spec['label_id']}_{kept:06d}.jpg"
        (OUT_DIR / filename).write_bytes(blob)
        rows.append(
            f"{filename},{spec['label_id']},{spec['code']},{prefix},"
            f"{spec['bn']},{spec['urgency']}\n"
        )
        kept += 1

    LABELS.write_text("".join(rows), encoding="utf-8")

    from collections import Counter

    by_class = Counter(r.split(",")[3] for r in rows[1:])
    print(f"  images   {kept} on disk (fold 1 of 5, no repeats)")
    print(f"  wrote {LABELS.relative_to(ROOT)}: {kept} labelled images")
    for cls, count in sorted(by_class.items()):
        print(f"    {cls:8} {count}")


if __name__ == "__main__":
    main()
