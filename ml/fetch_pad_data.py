# -*- coding: utf-8 -*-
"""Fetch the PAD-UFES-20 smartphone photographs of skin lesions.

About 2,300 lesion photographs taken with ordinary smartphones in Brazil,
each labelled with a diagnosis (six classes from basal cell carcinoma to
ordinary moles) and rich patient context - age, Fitzpatrick skin type,
body region, whether the lesion itches, grew, hurt, changed, bled.

Why this belongs here ahead of larger sets: every other lesion dataset we
serve is either dermatoscopic (HAM10000) or a web atlas of textbook
photographs (DermNet). Our users photograph a mole with the phone they own,
under whatever light they have. A model trained on exactly that kind of
image is the honest match for that input, and the Brazil study population
includes skin types the European datasets underrepresent.

Output: data/real/imaging/pad/ (images, gitignored) and
data/real/imaging/pad_labels.csv (committed).

    python ml/fetch_pad_data.py
"""
from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parents[1]
IMAGING = ROOT / "data" / "real" / "imaging"
CACHE = ROOT / "data" / "real" / "_cache"
OUT_DIR = IMAGING / "pad"
LABELS = IMAGING / "pad_labels.csv"

ZIP_URL = "https://data.mendeley.com/public-api/zip/zr7vgbcyr2/download/1"

# The published labels, with the referral reading we attach to each.
# BCC, SCC and melanoma are malignant; actinic keratosis is precancerous;
# the rest are benign. The Bangla names are the ones the response carries.
CLASSES = {
    "BCC": {"label_id": 0, "bn": "বেসাল সেল কার্সিনোমা (ত্বকের ক্যানসার)",
            "risk": "malignant"},
    "SCC": {"label_id": 1, "bn": "স্কোয়ামাস সেল কার্সিনোমা (ত্বকের ক্যানসার)",
            "risk": "malignant"},
    "MEL": {"label_id": 2, "bn": "মেলানোমা (ত্বকের ক্যানসার)",
            "risk": "malignant"},
    "ACK": {"label_id": 3, "bn": "অ্যাক্টিনিক কেরাটোসিস (প্রাক-ক্যানসার)",
            "risk": "precancerous"},
    "NEV": {"label_id": 4, "bn": "সাধারণ তিল",
            "risk": "benign"},
    "SEK": {"label_id": 5, "bn": "সেবোরিক কেরাটোসিস (নিরীহ)",
            "risk": "benign"},
}


def _fetch_zip() -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / "pad.zip"
    if cached.exists() and cached.stat().st_size > 3_000_000_000:
        return cached

    print("  downloading PAD-UFES-20 (3.6 GB)...")
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
    print("=== PAD-UFES-20 smartphone lesion photographs (CC BY 4.0)")

    archive = _fetch_zip()
    source = zipfile.ZipFile(archive)

    metadata = list(
        csv.DictReader(
            io.StringIO(source.read("metadata.csv").decode("utf-8"))
        )
    )
    by_img_id = {row["img_id"]: row for row in metadata}

    # The archive nests the photographs in three further zips. Each part is
    # read and released before the next opens: holding all three at once
    # needs more memory than a small machine has.
    image_zips = [
        name for name in source.namelist()
        if name.endswith(".zip") and "imgs_part" in name
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[str] = [
        "file,label_id,condition,condition_bn,risk,fitspatrick,age\n"
    ]
    kept = 0
    for name in image_zips:
        # Each part is over a gigabyte, so it goes to disk first and is
        # opened from there; zipfile seeks within a real file instead of
        # holding the whole archive in memory.
        part_path = CACHE / Path(name).name
        if not (part_path.exists()
                and part_path.stat().st_size == source.getinfo(name).file_size):
            with source.open(name) as src, part_path.open("wb") as dst:
                while True:
                    chunk = src.read(1 << 22)
                    if not chunk:
                        break
                    dst.write(chunk)
        inner = zipfile.ZipFile(part_path)

        for entry in inner.namelist():
            if not entry.lower().endswith((".png", ".jpg", ".jpeg")):
                continue
            img_id = Path(entry).name
            row = by_img_id.get(img_id)
            if row is None:
                continue
            spec = CLASSES.get(row["diagnostic"])
            if spec is None:
                continue
            with inner.open(entry) as fh:
                blob = fh.read()
            if not blob:
                continue
            filename = f"pad_{spec['label_id']}_{kept:06d}.png"
            (OUT_DIR / filename).write_bytes(blob)
            # The Fitzpatrick skin type travels with the image: without it
            # the skin-tone audit in ml/audit_skin_tones.py has nothing to
            # group by, and an unmeasured bias stays invisible.
            tone = (row.get("fitspatrick") or "").strip()
            tone = tone[:-2] if tone.endswith(".0") else tone
            rows.append(
                f"{filename},{spec['label_id']},{row['diagnostic']},"
                f"{spec['bn']},{spec['risk']},{tone},"
                f"{(row.get('age') or '').strip()}\n"
            )
            kept += 1
        inner.close()
        part_path.unlink()

    LABELS.write_text("".join(rows), encoding="utf-8")

    from collections import Counter

    by_class = Counter(r.split(",")[2] for r in rows[1:])
    print(f"  images   {kept} on disk")
    print(f"  wrote {LABELS.relative_to(ROOT)}: {kept} labelled images")
    for cls, count in sorted(by_class.items()):
        print(f"    {cls:4} {count}")


if __name__ == "__main__":
    main()
