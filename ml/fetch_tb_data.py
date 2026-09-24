# -*- coding: utf-8 -*-
"""Fetch the combined tuberculosis / pneumonia chest X-ray collection.

About 17,000 films in five folders - normal, pneumonia, tuberculosis,
COVID-19 and an "unknown" class - assembled on Hugging Face from several
long-public collections. The tuberculosis films trace back to the US
National Library of Medicine's Montgomery County and Shenzhen sets and the
Belarus/NIAID collections; the aggregation repo itself declares no licence,
which SOURCES.md records honestly rather than papering over.

Tuberculosis is the reason this dataset is here. Bangladesh records a few
hundred thousand new TB cases a year, and the only model we served before
this one could see pneumonia alone - a film showing the upper-lobe
infiltrates and cavitation typical of TB had no class to land in, so the
answer was a shrug. The "unknown" folder is dropped: its provenance cannot
be stated, and an unstateable class cannot be explained to a clinician.

Output: data/real/imaging/tb/ (images, gitignored) and
data/real/imaging/tb_labels.csv (committed).

    python ml/fetch_tb_data.py
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parents[1]
IMAGING = ROOT / "data" / "real" / "imaging"
CACHE = ROOT / "data" / "real" / "_cache"
OUT_DIR = IMAGING / "tb"
LABELS = IMAGING / "tb_labels.csv"

ZIP_URL = (
    "https://huggingface.co/datasets/"
    "DevVoyageR007/classify_Pneumonia_Tuberculosis_and_Normal__Non_Xray_"
    "chest_Xray_images/resolve/main/data.zip"
)

CLASSES = {
    "TUBERCULOSIS": {
        "label_id": 0,
        "bn": "যক্ষ্মা (টিবি) সন্দেহ",
    },
    "PNEUMONIA": {
        "label_id": 1,
        "bn": "নিউমোনিয়া",
    },
    "Corona Virus Disease": {
        "label_id": 2,
        "bn": "কোভিড-১৯ সন্দেহ",
    },
    "NORMAL": {
        "label_id": 3,
        "bn": "স্বাভাবিক",
    },
}


def _fetch_zip() -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / "tb_full.zip"
    if cached.exists() and cached.stat().st_size > 7_000_000_000:
        return cached

    print("  downloading the collection (7.7 GB)...")
    request = urllib.request.Request(ZIP_URL, headers={"User-Agent": "sasthosetu/1.0"})
    with urllib.request.urlopen(request, timeout=600) as response, \
            cached.open("wb") as out:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    return cached


def main() -> None:
    print("=== TB / pneumonia chest films (public collections, via Hugging Face)")

    archive = _fetch_zip()
    source = zipfile.ZipFile(archive)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[str] = ["file,label_id,condition,condition_bn\n"]
    extracted = 0
    for name in source.namelist():
        parts = [p for p in name.split("/") if p]
        if len(parts) < 2:
            continue
        folder = parts[-2]
        if folder not in CLASSES or not name.lower().endswith(
            (".jpg", ".jpeg", ".png", ".tif", ".tiff")
        ):
            continue
        spec = CLASSES[folder]
        blob = source.read(name)
        if not blob:
            continue
        filename = f"tb_{spec['label_id']}_{extracted:06d}.jpg"
        (OUT_DIR / filename).write_bytes(blob)
        rows.append(
            f"{filename},{spec['label_id']},{folder}," + spec["bn"] + "\n"
        )
        extracted += 1

    LABELS.write_text("".join(rows), encoding="utf-8")

    from collections import Counter

    by_class = Counter(r.split(",")[2] for r in rows[1:])
    print(f"  films    {extracted} on disk")
    print(f"  wrote {LABELS.relative_to(ROOT)}: {extracted} labelled films")
    for cls, count in sorted(by_class.items()):
        print(f"    {cls:22} {count}")


if __name__ == "__main__":
    main()
