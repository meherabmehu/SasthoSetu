# -*- coding: utf-8 -*-
"""Fetch the diabetic retinopathy fundus photographs.

About 2,750 retina photographs over five grades - healthy, mild, moderate,
severe and proliferative retinopathy. The parquet mirrors a long-public
Kaggle collection built from the EyePACS-style screening corpora (see
SOURCES.md for the honest provenance note).

Why this is here: diabetes prevalence in Bangladesh has crossed ten percent
of adults, and diabetic retinopathy is one of the leading causes of
preventable blindness among them. A retina photograph can be taken with a
handheld fundus camera in an upazila vision centre; the question the screen
answers is the one that screening programme asks - which photographs need
an ophthalmologist, and how soon.

Output: data/real/imaging/dr/ (images, gitignored) and
data/real/imaging/dr_labels.csv (committed).

    python ml/fetch_dr_data.py
"""
from __future__ import annotations

from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parents[1]
IMAGING = ROOT / "data" / "real" / "imaging"
CACHE = ROOT / "data" / "real" / "_cache"
OUT_DIR = IMAGING / "dr"
LABELS = IMAGING / "dr_labels.csv"

PARQUET_URL = (
    "https://huggingface.co/datasets/"
    "Rami/Diabetic_Retinopathy_Preprocessed_Dataset_256x256/resolve/main/"
    "data/train-00000-of-00001-7c2397e3a09be033.parquet"
)

CLASSES = {
    "Proliferate DR": {"label_id": 0, "code": "proliferative",
                       "bn": "প্রলিফারেটিভ রেটিনোপ্যাথি (গুরুতর)",
                       "urgency": "urgent"},
    "Severe DR": {"label_id": 1, "code": "severe",
                  "bn": "গুরুতর রেটিনোপ্যাথি",
                  "urgency": "urgent"},
    "Moderate DR": {"label_id": 2, "code": "moderate",
                    "bn": "মাঝারি রেটিনোপ্যাথি",
                    "urgency": "soon"},
    "Mild DR": {"label_id": 3, "code": "mild",
                "bn": "হালকা রেটিনোপ্যাথি",
                "urgency": "soon"},
    "Healthy": {"label_id": 4, "code": "healthy",
                "bn": "স্বাভাবিক রেটিনা",
                "urgency": "routine"},
}


def _fetch_parquet() -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / "dr.parquet"
    if cached.exists() and cached.stat().st_size > 300_000_000:
        return cached

    print("  downloading the parquet (364 MB)...")
    request = urllib.request.Request(
        PARQUET_URL, headers={"User-Agent": "sasthosetu/1.0"}
    )
    with urllib.request.urlopen(request, timeout=900) as response, \
            cached.open("wb") as out:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    return cached


def main() -> None:
    print("=== Diabetic retinopathy fundus photographs")

    archive = _fetch_parquet()

    import pyarrow.parquet as pq

    handle = pq.ParquetFile(archive)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[str] = ["file,label_id,code,condition,condition_bn,urgency\n"]
    kept = 0
    for group in range(handle.metadata.num_row_groups):
        table = handle.read_row_group(group, columns=["image", "label"])
        images = table.column("image").to_pylist()
        labels = table.column("label").to_pylist()
        for image, label in zip(images, labels, strict=True):
            spec = CLASSES.get(label)
            if spec is None:
                continue
            blob = image.get("bytes") if isinstance(image, dict) else None
            if not blob:
                continue
            filename = f"dr_{spec['label_id']}_{kept:06d}.jpg"
            (OUT_DIR / filename).write_bytes(blob)
            rows.append(
                f"{filename},{spec['label_id']},{spec['code']},{label},"
                f"{spec['bn']},{spec['urgency']}\n"
            )
            kept += 1
        del table, images, labels

    LABELS.write_text("".join(rows), encoding="utf-8")

    from collections import Counter

    by_class = Counter(r.split(",")[3] for r in rows[1:])
    print(f"  images   {kept} on disk")
    print(f"  wrote {LABELS.relative_to(ROOT)}: {kept} labelled images")
    for cls, count in sorted(by_class.items()):
        print(f"    {cls:16} {count}")


if __name__ == "__main__":
    main()
