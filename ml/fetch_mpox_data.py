# -*- coding: utf-8 -*-
"""Fetch the Monkeypox Skin Images Dataset (MSID).

Seven hundred and seventy photographs in four classes - monkeypox,
chickenpox, measles and normal skin - built at the Islamic University,
Kushtia, Bangladesh and published on Mendeley Data under CC BY 4.0.

Why this dataset belongs here ahead of most others: the viral exanthems that
circulate in Bangladesh are absent from DermNet's 23 conditions and from
HAM10000's seven pigmented-lesion classes entirely. A rash photograph
submitted to the skin check therefore had no path to "this could be
monkeypox" - the vocabulary to say it did not exist in any model we serve.

The classes are also deliberately confusable ones: monkeypox, chickenpox and
measles look alike in early photographs, which is exactly the mistake a
referral band has to be careful about. Over-referring a chickenpox is an
inconvenience; dismissing a monkeypox as normal is a public-health failure,
so the recall target is set on the monkeypox class the same way the other
image models weight their concerning classes.

Output: data/real/imaging/mpox/ (images, gitignored) and
data/real/imaging/mpox_labels.csv (committed).

    python ml/fetch_mpox_data.py
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parents[1]
IMAGING = ROOT / "data" / "real" / "imaging"
CACHE = ROOT / "data" / "real" / "_cache"
OUT_DIR = IMAGING / "mpox"
LABELS = IMAGING / "mpox_labels.csv"

# DOI 10.17632/r9bfpnvyxr.6 - the version is pinned so the class counts in
# the model card stay true.
ZIP_URL = "https://data.mendeley.com/public-api/zip/r9bfpnvyxr/download/6"

# Bangla names and referral weight for each class. Monkeypox is urgent
# (isolation and contact tracing must start early); chickenpox and measles
# are contagious and a doctor should confirm them, but the photographs of
# measles in particular are often mild presentations.
CLASSES = {
    "Monkeypox": {
        "label_id": 0,
        "bn": "মাংকিপক্স সন্দেহ",
        "urgency": "see_doctor_soon",
    },
    "Chickenpox": {
        "label_id": 1,
        "bn": "জলবসন্ত (চিকেনপক্স)",
        "urgency": "get_it_checked",
    },
    "Measles": {
        "label_id": 2,
        "bn": "হাম",
        "urgency": "get_it_checked",
    },
    "Normal": {
        "label_id": 3,
        "bn": "স্বাভাবিক ত্বক",
        "urgency": "watch_it",
    },
}


def _fetch_zip() -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / "mpox.zip"
    if cached.exists() and cached.stat().st_size > 50_000_000:
        return cached.read_bytes()

    print("  downloading MSID (54 MB)...")
    request = urllib.request.Request(ZIP_URL, headers={"User-Agent": "sasthosetu/1.0"})
    with urllib.request.urlopen(request, timeout=600) as response:
        payload = response.read()
    cached.write_bytes(payload)
    return payload


def main() -> None:
    print("=== Monkeypox skin images (MSID, CC BY 4.0)")

    payload = _fetch_zip()

    # The archive is a zip containing a second zip - the published layout.
    outer = zipfile.ZipFile(io.BytesIO(payload))
    inner_name = next(
        n for n in outer.namelist() if n.lower().endswith(".zip")
    )
    inner = zipfile.ZipFile(io.BytesIO(outer.read(inner_name)))

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    extracted = 0
    for name in inner.namelist():
        folder = name.strip("/").split("/")[-2] if "/" in name.strip("/") else ""
        if folder not in CLASSES or not name.lower().endswith(
            (".jpg", ".jpeg", ".png")
        ):
            continue
        spec = CLASSES[folder]
        blob = inner.read(name)
        if not blob:
            continue
        # Flat, numbered filenames keep the extraction simple and the label
        # file unambiguous.
        filename = f"mpox_{spec['label_id']}_{extracted:06d}.jpg"
        (OUT_DIR / filename).write_bytes(blob)
        rows.append(
            {
                "file": filename,
                "label_id": spec["label_id"],
                "condition": folder,
                "condition_bn": spec["bn"],
                "urgency": spec["urgency"],
            }
        )
        extracted += 1

    LABELS.write_text(
        "".join(
            [
                "file,label_id,condition,condition_bn,urgency\n",
                *[
                    f"{r['file']},{r['label_id']},{r['condition']},"
                    f"{r['condition_bn']},{r['urgency']}\n"
                    for r in rows
                ],
            ]
        ),
        encoding="utf-8",
    )

    from collections import Counter

    by_class = Counter(r["condition"] for r in rows)
    print(f"  images   {extracted} on disk")
    print(f"  wrote {LABELS.relative_to(ROOT)}: {extracted} labelled images")
    for cls, count in sorted(by_class.items()):
        print(f"    {cls:12} {count}")


if __name__ == "__main__":
    main()
