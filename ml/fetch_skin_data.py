# -*- coding: utf-8 -*-
"""Download HAM10000, the dermatoscopic image dataset.

10,015 real skin lesion photographs, each labelled with a diagnosis that was
confirmed by histopathology, follow-up, expert consensus or confocal
microscopy. Published by the Medical University of Vienna through Harvard
Dataverse.

    python ml/fetch_skin_data.py

Downloads about 2.8 GB into ``data/real/_cache`` and extracts the images to
``data/real/skin/images``. Neither is committed — the archives are large and
re-fetchable, and the derived feature table is what the training step needs.

Licence: CC BY-NC 4.0. Cite Tschandl, Rosendahl & Kittler, Scientific Data 5,
180161 (2018). Non-commercial use only, which is why the images stay out of
the repository.
"""
from __future__ import annotations

import csv
import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "real" / "_cache"
SKIN = ROOT / "data" / "real" / "skin"
IMAGES = SKIN / "images"

DATAVERSE = "https://dataverse.harvard.edu/api/access/datafile"

FILES = {
    "ham10000_metadata.csv": ("4338392", 830_428),
    "ham1.zip": ("3172585", 1_366_522_108),
    "ham2.zip": ("3172584", 1_403_566_547),
}

# The seven diagnostic classes, with what each means for a patient. Kept here
# rather than in the model so the wording can be reviewed by a clinician
# without touching training code.
CLASSES = {
    "akiec": ("Actinic keratosis / Bowen's disease", "precancerous"),
    "bcc": ("Basal cell carcinoma", "malignant"),
    "bkl": ("Benign keratosis", "benign"),
    "df": ("Dermatofibroma", "benign"),
    "mel": ("Melanoma", "malignant"),
    "nv": ("Melanocytic nevus (mole)", "benign"),
    "vasc": ("Vascular lesion", "benign"),
}


def _download(name: str, file_id: str, expected: int) -> Path:
    """Fetch one file, resolving the signed storage redirect first.

    Dataverse answers with a 303 to a pre-signed S3 URL that expires. Following
    it inside a batch, or reusing it later, yields a truncated file that still
    looks like a successful download — so the size is checked afterwards.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / name

    if target.exists() and target.stat().st_size >= expected * 0.99:
        print(f"  cached   {name} ({target.stat().st_size:,} bytes)")
        return target

    for attempt in range(1, 4):
        print(f"  fetching {name} (attempt {attempt}) ...", flush=True)
        url = subprocess.run(
            ["curl", "-s", "--max-time", "60", "-o", os.devnull,
             "-w", "%{redirect_url}", f"{DATAVERSE}/{file_id}"],
            capture_output=True, text=True, check=False,
        ).stdout.strip()

        if not url:
            url = f"{DATAVERSE}/{file_id}"

        subprocess.run(
            ["curl", "-sL", "--max-time", "1800", "--retry", "3",
             "-o", str(target), url],
            check=False,
        )

        size = target.stat().st_size if target.exists() else 0
        if size >= expected * 0.99:
            print(f"  saved    {name} ({size:,} bytes)")
            return target
        print(f"  short    {size:,} of {expected:,} bytes, retrying")

    raise RuntimeError(
        f"{name} downloaded incomplete after 3 attempts. The Dataverse "
        "storage redirect is signed and short-lived; try again, and make "
        "sure the download target is not a small tmpfs."
    )


def main() -> None:
    print("=== HAM10000 dermatoscopic images")

    metadata = _download("ham10000_metadata.csv", *FILES["ham10000_metadata.csv"])
    part1 = _download("ham1.zip", *FILES["ham1.zip"])
    part2 = _download("ham2.zip", *FILES["ham2.zip"])

    IMAGES.mkdir(parents=True, exist_ok=True)
    existing = {p.stem for p in IMAGES.glob("*.jpg")}
    extracted = 0

    for archive in (part1, part2):
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                if not member.lower().endswith(".jpg"):
                    continue
                stem = Path(member).stem
                if stem in existing:
                    continue
                with zf.open(member) as src:
                    (IMAGES / f"{stem}.jpg").write_bytes(src.read())
                extracted += 1

    total = len(list(IMAGES.glob("*.jpg")))
    print(f"  images   {total:,} on disk ({extracted:,} newly extracted)")

    # The published metadata is tab-separated with quoted values.
    rows = []
    with metadata.open(encoding="utf-8") as fh:
        for record in csv.DictReader(fh, delimiter="\t"):
            cleaned = {
                key: (value or "").strip().strip('"')
                for key, value in record.items()
            }
            if cleaned.get("image_id") and cleaned.get("dx"):
                rows.append(cleaned)

    SKIN.mkdir(parents=True, exist_ok=True)
    out = SKIN / "metadata.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["image_id", "diagnosis", "diagnosis_name",
                         "risk", "confirmed_by", "age", "sex", "site"])
        for row in rows:
            name, risk = CLASSES.get(row["dx"], (row["dx"], "unknown"))
            writer.writerow([
                row["image_id"], row["dx"], name, risk,
                row.get("dx_type", ""), row.get("age", ""),
                row.get("sex", ""), row.get("localization", ""),
            ])

    from collections import Counter
    counts = Counter(r["dx"] for r in rows)
    print(f"  wrote {out.relative_to(ROOT)}: {len(rows):,} labelled lesions")
    for code, count in counts.most_common():
        name, risk = CLASSES.get(code, (code, "?"))
        print(f"    {code:6} {count:5,}  {risk:12} {name}")

    if total < 9000:
        print(f"\nonly {total} images extracted, expected ~10,015")
        sys.exit(1)


if __name__ == "__main__":
    main()
