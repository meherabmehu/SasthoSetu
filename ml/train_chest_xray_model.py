# -*- coding: utf-8 -*-
"""Train the chest X-ray pneumonia screen.

Pneumonia is among the leading causes of death in children under five in
Bangladesh, and a chest X-ray is the common confirmatory test. Upazila health
complexes take the film; a radiologist to read it is often a district away.

This is a screen, not a report. It answers one question — does this film look
like pneumonia — and the threshold is set so that a film that might be
pneumonia is escalated rather than cleared. Missing a child with pneumonia and
missing a healthy child are not the same mistake.

Features are the same handcrafted block used for skin images, which works here
for a different reason: consolidation shows as increased opacity with reduced
local contrast in the lower lung fields, and those are exactly the intensity
and texture statistics the extractor already measures.

    python ml/train_chest_xray_model.py
    python ml/train_chest_xray_model.py --limit 2000

Output: backend/app/ai/artifacts/chest_xray_model.joblib, chest_xray_metrics.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
from PIL import Image
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    classification_report,
    f1_score,
    recall_score,
    roc_auc_score,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.skin_features import FEATURE_NAMES, extract_features  # noqa: E402

IMAGING = ROOT / "data" / "real" / "imaging"
IMAGES = IMAGING / "chest_xray"
LABELS = IMAGING / "chest_xray_labels.csv"
ART = ROOT / "backend" / "app" / "ai" / "artifacts"

SEED = 42

# A missed pneumonia is far more costly than a false alarm, so the operating
# point is chosen for recall on the pneumonia class rather than for accuracy.
TARGET_RECALL = 0.95


def _load(limit: int | None):
    with LABELS.open(encoding="utf-8") as fh:
        records = list(csv.DictReader(fh))

    if limit:
        rng = np.random.default_rng(SEED)
        index = rng.permutation(len(records))[:limit]
        records = [records[i] for i in index]

    features, findings, splits = [], [], []
    started = time.time()

    for position, record in enumerate(records, start=1):
        path = IMAGES / record["file"]
        if not path.exists():
            continue
        try:
            with Image.open(path) as image:
                vector = extract_features(image)
        except Exception:  # noqa: BLE001
            continue

        features.append(vector)
        findings.append(record["finding"])
        splits.append(record["split"])

        if position % 1000 == 0:
            rate = position / (time.time() - started)
            print(f"  {position:,}/{len(records):,} films ({rate:.0f}/s)",
                  flush=True)

    return (np.array(features, dtype=np.float32), np.array(findings),
            np.array(splits))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if not LABELS.exists():
        print(f"{LABELS.relative_to(ROOT)} is missing — run "
              "python ml/fetch_medical_datasets.py --only pneumonia first")
        raise SystemExit(1)

    print("Extracting film features")
    x, findings, splits = _load(args.limit)
    print(f"  {len(x):,} films, {x.shape[1]} features each")

    # The published split is honoured: these are separate patients, and
    # reshuffling would let the same child appear on both sides.
    fit_index = np.flatnonzero(splits == "train")
    val_index = np.flatnonzero(splits == "validation")
    test_index = np.flatnonzero(splits == "test")

    print(f"  train={len(fit_index):,} val={len(val_index):,} "
          f"test={len(test_index):,}")

    model = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.1, max_depth=8,
        class_weight="balanced", random_state=SEED,
    )
    model.fit(x[fit_index], findings[fit_index])

    classes = list(model.classes_)
    pneumonia_col = classes.index("pneumonia")

    val_score = model.predict_proba(x[val_index])[:, pneumonia_col]
    val_truth = findings[val_index] == "pneumonia"

    # Highest threshold that still reaches the target recall, so as few normal
    # films as possible are escalated while the misses stay rare.
    threshold = 0.05
    for candidate in sorted(np.linspace(0.05, 0.9, 86), reverse=True):
        if val_truth.sum() == 0:
            break
        flagged = val_score >= candidate
        if float((flagged & val_truth).sum() / val_truth.sum()) >= TARGET_RECALL:
            threshold = float(candidate)
            break

    print(f"  threshold = {threshold:.2f} "
          f"(validation, target recall {TARGET_RECALL:.0%})")

    test_score = model.predict_proba(x[test_index])[:, pneumonia_col]
    truth = findings[test_index]
    predicted = np.where(test_score >= threshold, "pneumonia", "normal")

    macro_f1 = f1_score(truth, predicted, average="macro")
    accuracy = float((predicted == truth).mean())
    pneumonia_recall = float(recall_score(
        truth == "pneumonia", predicted == "pneumonia", zero_division=0))
    missed = int(((truth == "pneumonia") & (predicted == "normal")).sum())
    auc = float(roc_auc_score(truth == "pneumonia", test_score))

    print(f"\ntest macro-F1 = {macro_f1:.4f}  accuracy = {accuracy:.4f}")
    print(f"AUC = {auc:.4f}")
    print(f"pneumonia recall = {pneumonia_recall:.4f}")
    print(f"missed pneumonia = {missed} "
          f"of {int((truth == 'pneumonia').sum())}")
    print()
    print(classification_report(truth, predicted, zero_division=0))

    ART.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": model, "features": FEATURE_NAMES, "threshold": threshold},
        ART / "chest_xray_model.joblib", compress=3,
    )
    (ART / "chest_xray_metrics.json").write_text(
        json.dumps({
            "test_macro_f1": round(float(macro_f1), 4),
            "test_accuracy": round(accuracy, 4),
            "auc": round(auc, 4),
            "pneumonia_recall": round(pneumonia_recall, 4),
            "missed_pneumonia": missed,
            "pneumonia_total": int((truth == "pneumonia").sum()),
            "threshold": round(threshold, 3),
            "test_size": int(len(test_index)),
            "n_films": int(len(x)),
            "seed": SEED,
        }, indent=2),
        encoding="utf-8",
    )
    print(f"\nartifacts -> {ART}")


if __name__ == "__main__":
    main()
