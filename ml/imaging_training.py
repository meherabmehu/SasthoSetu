"""Shared image features, duplicate-aware splits and validation calibration.

Patient IDs are used only when supplied by the source. Unknown patient identity
is explicitly reported; duplicate grouping is not a substitute for patient IDs.
"""
import csv
import hashlib
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.fft import dctn
from sklearn.model_selection import StratifiedGroupKFold

from app.ai.skin_features import FEATURE_NAMES, extract_features

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "real" / "_cache" / "features"


def _fingerprint(image):
    pixels = image.convert("RGB").resize((128, 128), Image.BILINEAR)
    digest = hashlib.sha256(pixels.tobytes()).hexdigest()
    gray = np.asarray(pixels.convert("L").resize((32, 32), Image.BILINEAR), dtype=float)
    frequencies = dctn(gray, norm="ortho")[:8, :8].ravel()
    bits = frequencies > np.median(frequencies[1:])
    value = sum(int(bit) << index for index, bit in enumerate(bits))
    return pixels, digest, f"{value:016x}"


def _signature(rows, image_dir):
    source = hashlib.sha256((ROOT / "backend/app/ai/skin_features.py").read_bytes())
    for row in rows:
        path = image_dir / row["file"]
        stat = path.stat()
        source.update(json.dumps([row, stat.st_size, stat.st_mtime_ns], sort_keys=True).encode())
    return source.hexdigest()


def _measure(path):
    try:
        with Image.open(path) as image:
            pixels, digest, phash = _fingerprint(image)
            if np.asarray(pixels).std() < 1:
                raise ValueError("Image has no usable pixel variation")
            return extract_features(pixels), {"pixel_sha256": digest, "phash": phash, "error": None}
    except (OSError, ValueError) as error:
        return np.zeros(len(FEATURE_NAMES)), {"pixel_sha256": None, "phash": None,
                                             "error": type(error).__name__}


def features_for_rows(rows, image_dir, dataset):
    """A cache is valid only for these ordered rows, image files and feature code."""
    CACHE.mkdir(parents=True, exist_ok=True)
    signature = _signature(rows, image_dir)
    prefix = CACHE / f"{dataset}-{signature}"
    meta_path = prefix.with_suffix(".json")
    npz_path = prefix.with_suffix(".npz")
    if meta_path.exists() and npz_path.exists():
        with np.load(npz_path, allow_pickle=False) as stored:
            print(f"  cached features for {len(rows):,} {dataset} images", flush=True)
            return stored["X"], stored["y"]
    features, fingerprints = [], []
    labels = [int(row["label_id"]) if "label_id" in row else row["diagnosis"] for row in rows]
    paths = [image_dir / row["file"] for row in rows]
    workers = max(1, min(4, int(os.environ.get("SASTHOSETU_FEATURE_WORKERS", os.cpu_count() or 1))))
    if len(paths) < 500:
        workers = 1
    pool = ProcessPoolExecutor(max_workers=workers) if workers > 1 else None
    try:
        measured = pool.map(_measure, paths, chunksize=16) if pool else map(_measure, paths)
        for index, (vector, fingerprint) in enumerate(measured):
            features.append(vector)
            fingerprints.append(fingerprint)
            if (index + 1) % 500 == 0:
                print(f"  features {index + 1:,}/{len(rows):,}: {dataset}", flush=True)
    finally:
        if pool:
            pool.shutdown()
    x, y = np.asarray(features, dtype=np.float32), np.asarray(labels)
    np.savez_compressed(npz_path, X=x, y=y)
    meta_path.write_text(json.dumps({"signature": signature, "images": fingerprints}), encoding="utf-8")
    return x, y


def make_split(rows, image_dir, dataset, artifact_dir, group_field=None, fraction=0.15):
    """Freeze subject/exact-pixel/perceptual components before fitting a model."""
    x, y = features_for_rows(rows, image_dir, dataset)
    signature = _signature(rows, image_dir)
    images = json.loads((CACHE / f"{dataset}-{signature}.json").read_text(encoding="utf-8"))["images"]
    count = len(rows)
    parent = list(range(count))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def join(a, b):
        parent[find(a)] = find(b)

    by_subject, by_pixels = {}, {}
    pixel_labels = {}
    for index, (row, info) in enumerate(zip(rows, images, strict=True)):
        subject = (row.get(group_field) or "").strip() if group_field else ""
        if subject.lower() in {"nan", "none"}:
            subject = ""
        if group_field in {"patient_id", "lesion_id"} and dataset in {"pad", "msld", "skin"} and not subject:
            raise ValueError(f"{dataset}: missing {group_field}; refresh original metadata first")
        if subject:
            if subject in by_subject:
                join(index, by_subject[subject])
            else:
                by_subject[subject] = index
        digest = info["pixel_sha256"]
        if digest:
            pixel_labels.setdefault(digest, set()).add(str(y[index]))
            if digest in by_pixels:
                join(index, by_pixels[digest])
            else:
                by_pixels[digest] = index
    excluded = {}
    for index, info in enumerate(images):
        digest = info["pixel_sha256"]
        if info["error"]:
            excluded[index] = "unreadable_or_blank"
        elif len(pixel_labels[digest]) > 1:
            excluded[index] = "conflicting_labels_for_same_pixels"
        elif by_pixels[digest] != index:
            excluded[index] = "exact_pixel_duplicate"
    eligible = np.array([i for i in range(count) if i not in excluded], dtype=int)
    hashes = np.array([int(images[i]["phash"], 16) for i in eligible], dtype=np.uint64)
    near_edges = 0
    # Bounded memory: one short vector, never an N-by-N distance matrix.
    for position, index in enumerate(eligible):
        distances = np.bitwise_count(hashes[:position] ^ hashes[position])
        neighbours = np.flatnonzero(distances <= 4)
        near_edges += len(neighbours)
        for other in neighbours:
            join(int(index), int(eligible[other]))
    groups = np.array([find(int(index)) for index in eligible])
    n_splits = max(3, round(1 / fraction))
    if len(set(groups)) < n_splits:
        raise ValueError("Not enough independent image/subject components for evaluation")
    folds = list(StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=42)
                 .split(x[eligible], y[eligible], groups))
    test_idx = eligible[folds[0][1]]
    val_idx = eligible[folds[1][1]]
    held = set(test_idx) | set(val_idx)
    train_idx = np.array([i for i in eligible if i not in held], dtype=int)
    all_labels = set(y[eligible])
    for name, indices in [("train", train_idx), ("validation", val_idx), ("test", test_idx)]:
        if set(y[indices]) != all_labels:
            raise ValueError(f"{dataset}: {name} lacks a class after grouping; need more independent cases")
    role = {int(i): name for name, part in [("train", train_idx), ("validation", val_idx),
                                           ("test", test_idx)] for i in part}
    partition_groups = [{find(int(i)) for i in part} for part in [train_idx, val_idx, test_idx]]
    if any(partition_groups[i] & partition_groups[j] for i in range(3) for j in range(i)):
        raise RuntimeError("A duplicate/subject component crossed evaluation partitions")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    fields = ["file", "label", "partition", "component", "subject_id", "pixel_sha256", "phash", "excluded_reason"]
    with (artifact_dir / f"{dataset}_evaluation.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for index, (row, info) in enumerate(zip(rows, images, strict=True)):
            writer.writerow({"file": row["file"], "label": str(y[index]),
                "partition": role.get(index, "excluded"), "component": find(index),
                "subject_id": row.get(group_field, "") if group_field else "",
                "pixel_sha256": info["pixel_sha256"], "phash": info["phash"],
                "excluded_reason": excluded.get(index, "")})
    source_subjects = sum(bool(row.get(group_field, "")) for row in rows) if group_field else 0
    audit = {"dataset": dataset, "seed": 42, "input_signature": signature,
        "source_rows": count, "eligible_images": len(eligible), "excluded_images": len(excluded),
        "exclusions": {reason: list(excluded.values()).count(reason) for reason in set(excluded.values())},
        "perceptual_hamming_limit": 4, "near_duplicate_edges": near_edges,
        "source_group_field": group_field, "rows_with_source_group": source_subjects,
        "source_groups_disjoint": bool(source_subjects),
        "all_subjects_known": source_subjects == count and group_field == "patient_id",
        "patient_identity_limitation": None if source_subjects == count and group_field == "patient_id"
            else "Some or all patient IDs are unavailable; duplicate separation is not patient-level validation.",
        "components_disjoint": True, "partition_sizes": {"train": len(train_idx),
            "validation": len(val_idx), "test": len(test_idx)},
        "partition_components": {name: len(groups) for name, groups in
            zip(["train", "validation", "test"], partition_groups, strict=True)}}
    (artifact_dir / f"{dataset}_split.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(f"  {dataset}: {len(excluded)} excluded; {near_edges} near-duplicate links; disjoint components", flush=True)
    return train_idx, val_idx, test_idx


def recall_threshold(scores, positives, target=0.90):
    """Highest observed threshold satisfying validation recall, including scores below .05."""
    scores = np.asarray(scores, dtype=float)
    positives = np.asarray(positives, dtype=bool)
    if not positives.any() or not np.isfinite(scores).all() or not 0 < target <= 1:
        raise ValueError("Finite validation scores and positive cases are required")
    values = np.sort(scores[positives])[::-1]
    selected = float(values[max(0, int(np.ceil(target * len(values))) - 1)])
    # Parallel tree probability accumulation can vary by a few ULPs between
    # calls. A tiny downward margin keeps the observed boundary case included.
    return max(0.0, selected - 1e-12)
