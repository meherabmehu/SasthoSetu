# -*- coding: utf-8 -*-
"""Train the skin lesion classifier on HAM10000.

The features are handcrafted rather than learned. That is a deliberate choice,
not a limitation of the machine: a dermatologist assessing a lesion looks at
asymmetry, border irregularity, colour variation and diameter — the ABCD rule —
and a model built on those same measurements can show a clinician exactly which
of them drove its answer. A convolutional network would very likely score
higher and would be impossible to interrogate the same way. For a tool that
must be reviewed before it is trusted, that trade is worth making.

Features extracted per image:

* colour statistics in RGB and HSV, over the lesion and the surrounding skin
* colour variegation — how many distinct colour clusters the lesion contains,
  which is what "multiple colours" means in the ABCD rule
* asymmetry across both axes of the segmented lesion
* border irregularity as the ratio of perimeter squared to area
* relative size of the lesion against the frame
* the contrast between lesion and surrounding skin

Output is a probability over seven diagnoses, collapsed to a risk band. The
band is what the interface shows: naming a specific cancer to a patient from a
phone photograph would be indefensible, but telling them a lesion needs a
dermatologist is useful and honest.

    python ml/train_skin_model.py
    python ml/train_skin_model.py --limit 2000     (quick check)

Output: backend/app/ai/artifacts/skin_model.joblib, skin_metrics.json
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
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    f1_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.skin_features import extract_features, FEATURE_NAMES  # noqa: E402

SKIN = ROOT / "data" / "real" / "skin"
IMAGES = SKIN / "images"
METADATA = SKIN / "metadata.csv"
ART = ROOT / "backend" / "app" / "ai" / "artifacts"

SEED = 42

# Malignant and precancerous diagnoses. Missing one of these is the error that
# matters, so recall on this group is reported separately from overall accuracy.
NEEDS_REVIEW = {"mel", "bcc", "akiec"}


def _load(limit: int | None) -> tuple[np.ndarray, np.ndarray, list[str]]:
    with METADATA.open(encoding="utf-8") as fh:
        records = list(csv.DictReader(fh))

    if limit:
        # Keep the class mix when sampling, or the rare classes vanish.
        rng = np.random.default_rng(SEED)
        by_class: dict[str, list[dict]] = {}
        for record in records:
            by_class.setdefault(record["diagnosis"], []).append(record)
        share = limit / len(records)
        records = []
        for group in by_class.values():
            take = max(20, int(len(group) * share))
            index = rng.permutation(len(group))[:take]
            records.extend(group[i] for i in index)

    features = []
    labels = []
    ids = []
    started = time.time()

    for position, record in enumerate(records, start=1):
        path = IMAGES / f"{record['image_id']}.jpg"
        if not path.exists():
            continue
        try:
            with Image.open(path) as image:
                vector = extract_features(image)
        except Exception:  # noqa: BLE001 - a corrupt file must not stop training
            continue

        features.append(vector)
        labels.append(record["diagnosis"])
        ids.append(record["image_id"])

        if position % 1000 == 0:
            rate = position / (time.time() - started)
            print(f"  {position:,}/{len(records):,} images "
                  f"({rate:.0f}/s)", flush=True)

    return np.array(features, dtype=np.float32), np.array(labels), ids


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None,
                        help="use a stratified subset, for a quick check")
    args = parser.parse_args()

    if not METADATA.exists():
        print(f"{METADATA.relative_to(ROOT)} is missing — "
              "run ml/fetch_skin_data.py first")
        raise SystemExit(1)

    print("Extracting image features")
    x, y, ids = _load(args.limit)
    print(f"  {len(x):,} images, {x.shape[1]} features each")

    rng = np.random.default_rng(SEED)
    order = rng.permutation(len(x))
    cut_val = int(len(x) * 0.8)
    cut_test = int(len(x) * 0.9)
    train_idx = order[:cut_val]
    val_idx = order[cut_val:cut_test]
    test_idx = order[cut_test:]

    print(f"  train={len(train_idx):,} val={len(val_idx):,} "
          f"test={len(test_idx):,}")

    candidates = {
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.1, max_depth=8,
            class_weight="balanced", random_state=SEED,
        ),
        "logistic_regression": Pipeline([
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(
                max_iter=2000, class_weight="balanced",
                multi_class="multinomial", random_state=SEED,
            )),
        ]),
    }

    scores = {}
    fitted = {}
    for name, model in candidates.items():
        model.fit(x[train_idx], y[train_idx])
        predicted = model.predict(x[val_idx])
        score = f1_score(y[val_idx], predicted, average="macro")
        scores[name] = round(float(score), 4)
        fitted[name] = model
        print(f"  {name:24} val macro-F1 = {score:.4f}")

    best_name = max(scores, key=scores.get)
    model = fitted[best_name]
    print(f"selected: {best_name}")

    predicted = model.predict(x[test_idx])
    truth = y[test_idx]

    macro_f1 = f1_score(truth, predicted, average="macro")
    accuracy = float((predicted == truth).mean())

    # The clinically important number: of the lesions that were malignant or
    # precancerous, how many did the model route to a dermatologist?
    #
    # Taking the single most likely class misses about half of them, because
    # melanoma is heavily outnumbered by ordinary moles and rarely wins the
    # argmax outright. What the interface actually needs is not "which of the
    # seven is it" but "does this need a doctor", so the referral decision is
    # made by summing the probability across the concerning classes and
    # comparing that to a threshold chosen on the validation split.
    classes = list(model.classes_)
    review_columns = [i for i, c in enumerate(classes) if c in NEEDS_REVIEW]

    val_probabilities = model.predict_proba(x[val_idx])
    val_review_score = val_probabilities[:, review_columns].sum(axis=1)
    val_review_truth = np.isin(y[val_idx], list(NEEDS_REVIEW))

    # Choose the lowest threshold that reaches the target recall, so as few
    # benign lesions as possible are sent for review while still catching the
    # ones that matter.
    target_recall = 0.90
    threshold = 0.02
    # Walk from strict to lenient and stop at the first threshold that reaches
    # the target, which is the highest one that still catches enough cases and
    # therefore flags the fewest benign lesions.
    for candidate in sorted(np.linspace(0.02, 0.9, 89), reverse=True):
        if val_review_truth.sum() == 0:
            break
        flagged = val_review_score >= candidate
        recall = float((flagged & val_review_truth).sum()
                       / val_review_truth.sum())
        if recall >= target_recall:
            threshold = float(candidate)
            break
    print(f"referral threshold = {threshold:.2f} "
          f"(chosen on validation for >={target_recall:.0%} recall)")

    review_truth = np.isin(truth, list(NEEDS_REVIEW))
    test_probabilities = model.predict_proba(x[test_idx])
    review_pred = (
        test_probabilities[:, review_columns].sum(axis=1) >= threshold
    )
    review_recall = float(recall_score(review_truth, review_pred,
                                       zero_division=0))
    review_precision = float(
        (review_pred & review_truth).sum() / max(review_pred.sum(), 1)
    )
    print(f"referral precision = {review_precision:.4f} "
          f"({int(review_pred.sum())} of {len(truth)} flagged)")

    try:
        probabilities = model.predict_proba(x[test_idx])
        auc = float(roc_auc_score(truth, probabilities,
                                  multi_class="ovr", average="macro"))
    except Exception:  # noqa: BLE001
        auc = None

    print(f"\ntest macro-F1 = {macro_f1:.4f}  accuracy = {accuracy:.4f}")
    print(f"malignant/precancerous recall = {review_recall:.4f}")
    if auc:
        print(f"macro AUC = {auc:.4f}")
    print()
    print(classification_report(truth, predicted, zero_division=0))

    ART.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": model, "features": FEATURE_NAMES,
         "classes": sorted(set(y)),
         "referral_threshold": threshold,
         "referral_classes": sorted(NEEDS_REVIEW)},
        ART / "skin_model.joblib", compress=3,
    )
    (ART / "skin_metrics.json").write_text(
        json.dumps({
            "selected_model": best_name,
            "validation_macro_f1": scores,
            "test_macro_f1": round(float(macro_f1), 4),
            "test_accuracy": round(accuracy, 4),
            "malignant_recall": round(review_recall, 4),
            "malignant_precision": round(review_precision, 4),
            "referral_threshold": round(threshold, 3),
            "macro_auc": round(auc, 4) if auc else None,
            "test_size": int(len(test_idx)),
            "n_images": int(len(x)),
            "n_features": int(x.shape[1]),
            "seed": SEED,
        }, indent=2),
        encoding="utf-8",
    )
    print(f"\nartifacts -> {ART}")


if __name__ == "__main__":
    main()
