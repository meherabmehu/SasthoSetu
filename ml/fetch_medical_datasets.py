# -*- coding: utf-8 -*-
"""Download the public medical imaging datasets the platform trains on.

HAM10000 alone covers seven pigmented lesion types — melanoma, moles and a few
related things. That is a narrow slice of dermatology and, more to the point, a
slice that matters less in Bangladesh than fungal infection, scabies, eczema and
acne. A tool that confidently reports "ordinary mole" when shown ringworm is
worse than no tool at all.

So several sources are combined:

    dermnet       23 skin conditions, 15,557 clinical photographs. Includes
                  what people here actually present with: tinea, scabies,
                  eczema, acne, bacterial infection, nail fungus. These are
                  ordinary photographs rather than dermatoscope images, which
                  is much closer to what a phone camera produces. MIT licence.

    ham10000      10,015 dermatoscopic images with histopathology-confirmed
                  diagnoses. Narrow, but very well labelled — this is what
                  gives malignancy detection its evidence.
                  Fetched separately by ml/fetch_skin_data.py.

    pneumonia     5,856 paediatric chest X-rays, normal against pneumonia.
                  Pneumonia is a leading cause of under-five death in
                  Bangladesh. CC BY 4.0.

Every source is public and needs no credentials. Archives land in
``data/real/_cache`` and images are extracted under ``data/real/imaging``;
neither is committed, because they are large and several carry non-commercial
terms. The derived label tables are committed.

    python ml/fetch_medical_datasets.py
    python ml/fetch_medical_datasets.py --only dermnet
    python ml/fetch_medical_datasets.py --list
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "real" / "_cache"
IMAGING = ROOT / "data" / "real" / "imaging"

HF = "https://huggingface.co/datasets"

SOURCES = {
    "dermnet": {
        "repo": "Muzmmillcoste/dermnet",
        "splits": {"train": 3, "test": 1},
        "licence": "MIT",
        "about": "23 skin conditions, clinical photographs",
    },
    "pneumonia": {
        "repo": "mmenendezg/pneumonia_x_ray",
        "splits": {"train": 1, "validation": 1, "test": 1},
        "licence": "CC BY 4.0",
        "about": "paediatric chest X-rays, normal vs pneumonia",
    },
}

# Which of the 23 DermNet classes matter most, grouped by what the person
# should do rather than by pathology. This mapping is a clinical judgement and
# is the part a doctor should review first.
DERMNET_URGENCY = {
    "Actinic Keratosis Basal Cell Carcinoma and other Malignant Lesions":
        "see_doctor_soon",
    "Melanoma Skin Cancer Nevi and Moles": "see_doctor_soon",
    "Cellulitis Impetigo and other Bacterial Infections": "see_doctor_soon",
    "Vasculitis Photos": "see_doctor_soon",
    "Bullous Disease Photos": "see_doctor_soon",
    "Lupus and other Connective Tissue diseases": "see_doctor_soon",
    "Systemic Disease": "see_doctor_soon",
    "Herpes HPV and other STDs Photos": "get_it_checked",
    "Psoriasis pictures Lichen Planus and related diseases": "get_it_checked",
    "Scabies Lyme Disease and other Infestations and Bites": "get_it_checked",
    "Tinea Ringworm Candidiasis and other Fungal Infections": "get_it_checked",
    "Nail Fungus and other Nail Disease": "get_it_checked",
    "Atopic Dermatitis Photos": "get_it_checked",
    "Eczema Photos": "get_it_checked",
    "Exanthems and Drug Eruptions": "get_it_checked",
    "Hair Loss Photos Alopecia and other Hair Diseases": "watch_it",
    "Light Diseases and Disorders of Pigmentation": "watch_it",
    "Poison Ivy Photos and other Contact Dermatitis": "watch_it",
    "Seborrheic Keratoses and other Benign Tumors": "watch_it",
    "Urticaria Hives": "watch_it",
    "Warts Molluscum and other Viral Infections": "watch_it",
    "Vascular Tumors": "watch_it",
    "Acne and Rosacea Photos": "watch_it",
}

# Short Bangla names, so a result is readable by someone who does not read
# English clinical wording.
DERMNET_BN = {
    "Acne and Rosacea Photos": "ব্রণ ও রোসেশিয়া",
    "Actinic Keratosis Basal Cell Carcinoma and other Malignant Lesions":
        "ত্বকের ক্যানসার বা প্রাক-ক্যানসার",
    "Atopic Dermatitis Photos": "অ্যাটোপিক ডার্মাটাইটিস (একজিমা)",
    "Bullous Disease Photos": "ফোসকাজনিত রোগ",
    "Cellulitis Impetigo and other Bacterial Infections":
        "ব্যাকটেরিয়া সংক্রমণ (সেলুলাইটিস)",
    "Eczema Photos": "একজিমা",
    "Exanthems and Drug Eruptions": "ওষুধজনিত র‍্যাশ",
    "Hair Loss Photos Alopecia and other Hair Diseases": "চুল পড়া",
    "Herpes HPV and other STDs Photos": "হারপিস / যৌনবাহিত সংক্রমণ",
    "Light Diseases and Disorders of Pigmentation": "ত্বকের রং পরিবর্তন",
    "Lupus and other Connective Tissue diseases": "লুপাস",
    "Melanoma Skin Cancer Nevi and Moles": "তিল ও মেলানোমা",
    "Nail Fungus and other Nail Disease": "নখের ছত্রাক",
    "Poison Ivy Photos and other Contact Dermatitis": "সংস্পর্শজনিত র‍্যাশ",
    "Psoriasis pictures Lichen Planus and related diseases": "সোরিয়াসিস",
    "Scabies Lyme Disease and other Infestations and Bites":
        "খোসপাঁচড়া (স্ক্যাবিস)",
    "Seborrheic Keratoses and other Benign Tumors": "নিরীহ আঁচিল",
    "Systemic Disease": "শরীরের ভেতরের রোগের ত্বকীয় লক্ষণ",
    "Tinea Ringworm Candidiasis and other Fungal Infections":
        "দাদ ও ছত্রাক সংক্রমণ",
    "Urticaria Hives": "আমবাত",
    "Vascular Tumors": "রক্তনালীর গুটি",
    "Vasculitis Photos": "রক্তনালীর প্রদাহ",
    "Warts Molluscum and other Viral Infections": "আঁচিল ও ভাইরাস সংক্রমণ",
}

PNEUMONIA_BN = {"normal": "স্বাভাবিক", "pneumonia": "নিউমোনিয়া"}


def _class_names(repo: str) -> list[str]:
    """Read the label names from the Hugging Face dataset server."""
    url = f"https://datasets-server.huggingface.co/info?dataset={repo}"
    payload = subprocess.run(
        ["curl", "-sL", "--max-time", "90", url],
        capture_output=True, text=True, check=False,
    ).stdout
    try:
        configs = json.loads(payload)["dataset_info"]
        config = configs.get("default") or next(iter(configs.values()))
        return list(config["features"]["label"]["names"])
    except Exception:  # noqa: BLE001
        return []


def _fetch_parquet(repo: str, split: str, index: int) -> Path | None:
    """One parquet shard on disk.

    The path is returned rather than the bytes: these shards are 400 MB and
    this has to run on a machine with 2 GB of RAM, so nothing ever reads a
    whole one into memory.
    """
    name = f"{repo.replace('/', '_')}_{split}_{index:04d}.parquet"
    cached = CACHE / name
    if cached.exists() and cached.stat().st_size > 1000:
        return cached

    CACHE.mkdir(parents=True, exist_ok=True)
    # Hugging Face answers with a signed CDN redirect that expires, so the URL
    # is resolved and fetched in one request rather than reused.
    url = (f"{HF}/{repo}/resolve/refs%2Fconvert%2Fparquet/"
           f"default/{split}/{index:04d}.parquet")

    subprocess.run(
        ["curl", "-sL", "--max-time", "900", "--retry", "2",
         "-o", str(cached), url],
        check=False,
    )
    if not cached.exists() or cached.stat().st_size < 1000:
        if cached.exists():
            cached.unlink()
        return None
    return cached


def _extract(path: Path, out_dir: Path, prefix: str,
             start: int) -> list[tuple[str, int]]:
    """Write each image out as a file, returning (filename, label) pairs.

    Read one row group at a time. Reading the whole table needs several times
    the file size in RAM, which is what killed this on a small machine.
    """
    import pyarrow.parquet as pq

    out_dir.mkdir(parents=True, exist_ok=True)
    handle = pq.ParquetFile(path)
    written: list[tuple[str, int]] = []
    offset = 0

    for group in range(handle.metadata.num_row_groups):
        table = handle.read_row_group(group, columns=["image", "label"])
        images = table.column("image").to_pylist()
        labels = table.column("label").to_pylist()

        for image, label in zip(images, labels, strict=True):
            blob = image.get("bytes") if isinstance(image, dict) else None
            offset += 1
            if not blob:
                continue
            filename = f"{prefix}_{start + offset:06d}.jpg"
            (out_dir / filename).write_bytes(blob)
            written.append((filename, int(label)))

        del table, images, labels

    return written


def fetch_dermnet() -> Path:
    print("\n=== DermNet: 23 skin conditions (MIT)")
    names = _class_names(SOURCES["dermnet"]["repo"])
    if not names:
        raise RuntimeError("could not read the DermNet class list")
    print(f"  {len(names)} classes")

    out_dir = IMAGING / "dermnet"
    rows: list[tuple[str, int, str]] = []
    total = 0

    for split, shards in SOURCES["dermnet"]["splits"].items():
        for index in range(shards):
            shard = _fetch_parquet(SOURCES["dermnet"]["repo"], split, index)
            if shard is None:
                print(f"  {split}/{index}: unavailable")
                continue
            pairs = _extract(shard, out_dir, split, total)
            total += len(pairs)
            rows.extend((f, label, split) for f, label in pairs)
            print(f"  {split}/{index}: {len(pairs):,} images", flush=True)

    if not rows:
        raise RuntimeError("no DermNet images were extracted")

    meta = IMAGING / "dermnet_labels.csv"
    with meta.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["file", "label_id", "condition",
                         "condition_bn", "urgency", "split"])
        for filename, label, split in rows:
            condition = names[label] if label < len(names) else str(label)
            writer.writerow([
                filename, label, condition,
                DERMNET_BN.get(condition, condition),
                DERMNET_URGENCY.get(condition, "get_it_checked"),
                split,
            ])

    print(f"  wrote {meta.relative_to(ROOT)}: {len(rows):,} images")
    return meta


def fetch_pneumonia() -> Path:
    print("\n=== Chest X-ray: pneumonia vs normal (CC BY 4.0)")
    names = _class_names(SOURCES["pneumonia"]["repo"]) or ["normal", "pneumonia"]

    out_dir = IMAGING / "chest_xray"
    rows: list[tuple[str, int, str]] = []
    total = 0

    for split, shards in SOURCES["pneumonia"]["splits"].items():
        for index in range(shards):
            shard = _fetch_parquet(SOURCES["pneumonia"]["repo"], split, index)
            if shard is None:
                print(f"  {split}/{index}: unavailable")
                continue
            pairs = _extract(shard, out_dir, split, total)
            total += len(pairs)
            rows.extend((f, label, split) for f, label in pairs)
            print(f"  {split}/{index}: {len(pairs):,} images", flush=True)

    if not rows:
        raise RuntimeError("no chest X-ray images were extracted")

    meta = IMAGING / "chest_xray_labels.csv"
    with meta.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["file", "label_id", "finding", "finding_bn", "split"])
        for filename, label, split in rows:
            finding = (names[label] if label < len(names)
                       else str(label)).lower()
            writer.writerow([filename, label, finding,
                             PNEUMONIA_BN.get(finding, finding), split])

    print(f"  wrote {meta.relative_to(ROOT)}: {len(rows):,} images")
    return meta


FETCHERS = {"dermnet": fetch_dermnet, "pneumonia": fetch_pneumonia}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", choices=sorted(FETCHERS))
    parser.add_argument("--list", action="store_true",
                        help="describe the sources and exit")
    args = parser.parse_args()

    if args.list:
        for name, source in SOURCES.items():
            print(f"{name:12} {source['licence']:12} {source['about']}")
            print(f"{'':12} {HF}/{source['repo']}")
        return

    failures = []
    for name in (args.only or sorted(FETCHERS)):
        try:
            FETCHERS[name]()
        except Exception as error:  # noqa: BLE001
            print(f"  FAILED {name}: {error}")
            failures.append(name)

    if IMAGING.exists():
        entries = {}
        for path in sorted(IMAGING.glob("*.csv")):
            with path.open(encoding="utf-8") as fh:
                entries[path.name] = sum(1 for _ in fh) - 1
        (IMAGING / "MANIFEST.json").write_text(
            json.dumps(entries, indent=2) + "\n", encoding="utf-8")
        print(f"\nmanifest -> {(IMAGING / 'MANIFEST.json').relative_to(ROOT)}")

    if failures:
        print(f"\n{len(failures)} source(s) unavailable: {', '.join(failures)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
