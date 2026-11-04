# -*- coding: utf-8 -*-
"""Fetch the combined tuberculosis / pneumonia chest X-ray collection.

About 17,000 films in five folders - normal, pneumonia, tuberculosis,
COVID-19 and an "unknown" class - assembled on Hugging Face from several
long-public collections. Some filenames resemble established chest-film sets,
but complete image-level lineage is unavailable. The aggregation repo declares
no licence; SOURCES.md records that limitation.

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
import argparse
import csv
import hashlib
import io
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMAGING = ROOT / "data" / "real" / "imaging"
CACHE = ROOT / "data" / "real" / "_cache"
OUT_DIR = IMAGING / "tb"
LABELS = IMAGING / "tb_labels.csv"

ZIP_URL = (
    "https://huggingface.co/datasets/"
    "DevVoyageR007/classify_Pneumonia_Tuberculosis_and_Normal__Non_Xray_"
    "chest_Xray_images/resolve/8bc28dc33778ce84d228bf04b798c0828ad64e18/data.zip"
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
    from download_ranges import download
    return download(ZIP_URL, CACHE / "tb_full.zip", kind="zip")


def main() -> None:
    print("=== TB / pneumonia chest films (public collections, via Hugging Face)")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="use an already downloaded source archive")
    parser.add_argument("--compact", action="store_true",
                        help="store lossless PNGs at the runtime's 128x128 input size")
    args = parser.parse_args()
    archive = args.archive or _fetch_zip()
    source = zipfile.ZipFile(archive)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
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
        suffix = ".jpg"
        source_hash = hashlib.sha256(blob).hexdigest()
        if args.compact:
            from PIL import Image
            with Image.open(io.BytesIO(blob)) as image:
                reduced = image.convert("RGB").resize((128, 128), Image.BILINEAR)
                output = io.BytesIO()
                reduced.save(output, format="PNG")
                blob = output.getvalue()
                suffix = ".png"
        filename = f"tb_{spec['label_id']}_{extracted:06d}{suffix}"
        (OUT_DIR / filename).write_bytes(blob)
        stem = Path(name).stem
        patient = re.match(r"(person\d+)_", stem, re.I)
        nlm = re.match(r"((?:CHN|MCU)CXR_\d+)_", stem, re.I)
        normal = re.match(r"((?:NORMAL2-)?IM-\d+)-", stem, re.I)
        known_id = patient or nlm or normal
        rows.append({"file": filename, "label_id": spec["label_id"], "condition": folder,
                     "condition_bn": spec["bn"], "source_file": name,
                     "source_sha256": source_hash,
                     "patient_id": known_id.group(1) if known_id else "",
                     "storage": "runtime_128_png" if args.compact else "source_bytes"})
        extracted += 1
        if extracted % 1000 == 0:
            print(f"  extracted {extracted} films", flush=True)

    if not rows:
        raise ValueError("No supported chest-film classes found; existing labels were not changed")
    with LABELS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    from collections import Counter

    by_class = Counter(row["condition"] for row in rows)
    print(f"  films    {extracted} on disk")
    print(f"  wrote {LABELS.relative_to(ROOT)}: {extracted} labelled films")
    for cls, count in sorted(by_class.items()):
        print(f"    {cls:22} {count}")


if __name__ == "__main__":
    main()
