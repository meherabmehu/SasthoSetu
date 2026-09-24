# -*- coding: utf-8 -*-
"""Fetch the oral cancer photographs.

Ten thousand photographs of the inside of the mouth in two classes - oral
squamous cell carcinoma and normal tissue - mirrored on Hugging Face. The
collection behind this mirror is a Kaggle oral-cancer set assembled from
public clinical photography; the mirror itself declares no licence, which
SOURCES.md records as it is.

Why this is here: oral cancer is among the commonest cancers in Bangladesh,
driven by betel-quid and tobacco chewing, and it is typically caught late
precisely because the inside of a mouth is not something anyone photographs
early. A village pharmacist or a health worker with a phone torch can take
this photograph; the screen answers the screening question - does this
mouth need a specialist to look at it today?

Output: data/real/imaging/oral/ (images, gitignored) and
data/real/imaging/oral_labels.csv (committed).

    python ml/fetch_oral_data.py
"""
from __future__ import annotations

from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parents[1]
IMAGING = ROOT / "data" / "real" / "imaging"
CACHE = ROOT / "data" / "real" / "_cache"
OUT_DIR = IMAGING / "oral"
LABELS = IMAGING / "oral_labels.csv"

REPO = "Alwaly/Oral_Cancer-cancer"
SHARDS = [
    "data/train-00000-of-00002.parquet",
    "data/train-00001-of-00002.parquet",
]

CLASSES = {
    "oral_scc": {
        "label_id": 0, "code": "oral_scc",
        "bn": "মুখের ক্যানসারের মতো পরিবর্তন (OSC সন্দেহ)",
        "urgency": "urgent",
    },
    "oral_normal": {
        "label_id": 1, "code": "oral_normal",
        "bn": "স্বাভাবিক মুখের ভেতর",
        "urgency": "routine",
    },
}


def _fetch(shard: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"oral_{shard.split('-')[1]}.parquet"
    if cached.exists() and cached.stat().st_size > 100_000_000:
        return cached

    url = (f"https://huggingface.co/datasets/{REPO}/resolve/main/{shard}")
    print(f"  downloading {shard}...")
    request = urllib.request.Request(url, headers={"User-Agent": "sasthosetu/1.0"})
    with urllib.request.urlopen(request, timeout=900) as response, \
            cached.open("wb") as out:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    return cached


def main() -> None:
    print("=== Oral cancer photographs (public collection, via Hugging Face)")

    import pyarrow.parquet as pq

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[str] = ["file,label_id,code,condition,condition_bn,urgency\n"]
    kept = 0

    for shard in SHARDS:
        path = _fetch(shard)
        handle = pq.ParquetFile(path)
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
                filename = f"oral_{spec['label_id']}_{kept:06d}.jpg"
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
        print(f"    {cls:14} {count}")


if __name__ == "__main__":
    main()
