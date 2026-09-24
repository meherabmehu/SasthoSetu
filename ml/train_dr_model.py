# -*- coding: utf-8 -*-
"""Train the diabetic retinopathy screen on fundus photographs.

Five grades over 2,750 retina photographs. The features are the same 32
handcrafted measurements the other image models use, and the decision the
screen serves is the one a screening programme actually makes: does this
photograph need an ophthalmologist, and how soon?

The safety asymmetry is the familiar one, in its sharpest form: a missed
proliferative retina is blindness that a timely laser would have prevented,
while an over-referred healthy retina costs one dilated examination. The
referral decision therefore sums the probability across all retinopathy
grades, weighted toward the sight-threatening ones, and compares it to a
threshold chosen on validation for a high recall of the severe grades.

Output: backend/app/ai/artifacts/dr_model.joblib, dr_metrics.json

    python ml/train_dr_model.py
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import joblib
import numpy as np
from PIL import Image
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.skin_features import extract_features, FEATURE_NAMES  # noqa: E402

IMAGING = ROOT / "data" / "real" / "imaging"
IMAGES = IMAGING / "dr"
LABELS = IMAGING / "dr_labels.csv"
ART = ROOT / "backend" / "app" / "ai" / "artifacts"

SEED = 42

CONDITIONS = [
    (0, "Proliferative DR", "প্রলিফারেটিভ রেটিনোপ্যাথি"),
    (1, "Severe DR", "গুরুতর রেটিনোপ্যাথি"),
    (2, "Moderate DR", "মাঝারি রেটিনোপ্যাথি"),
    (3, "Mild DR", "হালকা রেটিনোপ্যাথি"),
    (4, "Healthy", "স্বাভাবিক রেটিনা"),
]
CODES = {
    0: "proliferative", 1: "severe", 2: "moderate",
    3: "mild", 4: "healthy",
}

# Sight-threatening grades carry the full weight; any retinopathy at all
# still carries some, because even mild disease means a diabetic's eyes
# need watching.
CONCERN_WEIGHT = {0: 1.0, 1: 1.0, 2: 0.6, 3: 0.3, 4: 0.0}


def load_rows() -> list[dict]:
    with LABELS.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def features_for(rows: list[dict]):
    X = np.zeros((len(rows), len(FEATURE_NAMES)), dtype=np.float32)
    y = np.zeros(len(rows), dtype=np.int64)
    started = time.time()
    for index, row in enumerate(rows):
        image = Image.open(IMAGES / row["file"]).convert("RGB")
        X[index] = extract_features(image)
        y[index] = int(row["label_id"])
        if (index + 1) % 500 == 0:
            rate = (index + 1) / (time.time() - started)
            print(f"  {index + 1}/{len(rows)} images ({rate:.0f}/s)")
    return X, y


def split_by_class(y: np.ndarray, seed: int, val_frac=0.15, test_frac=0.15):
    rng = np.random.default_rng(seed)
    train_idx, val_idx, test_idx = [], [], []
    for cls in np.unique(y):
        idx = np.where(y == cls)[0]
        rng.shuffle(idx)
        n = len(idx)
        n_val = max(1, int(round(n * val_frac)))
        n_test = max(1, int(round(n * test_frac)))
        val_idx.extend(idx[:n_val])
        test_idx.extend(idx[n_val:n_val + n_test])
        train_idx.extend(idx[n_val + n_test:])
    return (
        np.array(sorted(train_idx)),
        np.array(sorted(val_idx)),
        np.array(sorted(test_idx)),
    )


def concern_score(proba: np.ndarray) -> np.ndarray:
    return sum(w * proba[:, c] for c, w in CONCERN_WEIGHT.items())


def main() -> None:
    print("Extracting image features")
    rows = load_rows()
    X, y = features_for(rows)
    print(f"  {len(rows)} images, {X.shape[1]} features each")

    train_idx, val_idx, test_idx = split_by_class(y, SEED)
    print(f"train={len(train_idx)} val={len(val_idx)} test={len(test_idx)}")

    candidates = {
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            random_state=SEED
        ),
        "logistic_regression": Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=3000,
                        class_weight="balanced",
                        random_state=SEED,
                    ),
                ),
            ]
        ),
    }

    for model in candidates.values():
        model.fit(X[train_idx], y[train_idx])

    best_name, best_model, best_f1 = None, None, -1.0
    for name, model in candidates.items():
        val_f1 = f1_score(
            y[val_idx], model.predict(X[val_idx]), average="macro"
        )
        print(f"  {name:24} val macro-F1 = {val_f1:.4f}")
        if val_f1 > best_f1:
            best_name, best_model, best_f1 = name, model, val_f1
    print(f"selected: {best_name}")

    proba_val = best_model.predict_proba(X[val_idx])
    scores_val = concern_score(proba_val)
    sight_threatening_val = np.isin(y[val_idx], [0, 1])

    threshold = 0.5
    for candidate in np.arange(0.05, 0.95, 0.01):
        caught = (scores_val[sight_threatening_val] >= candidate).mean()
        if caught >= 0.90:
            threshold = float(candidate)
    print(
        f"referral threshold = {threshold:.2f} "
        f"(validation, >=90% sight-threatening recall)"
    )

    proba_test = best_model.predict_proba(X[test_idx])
    scores_test = concern_score(proba_test)
    pred_test = best_model.predict(X[test_idx])

    sight_recall = recall_score(
        np.isin(y[test_idx], [0, 1]), scores_test >= threshold
    )
    any_dr_recall = recall_score(
        y[test_idx] != 4, scores_test >= threshold / 2
    )
    flagged = int((scores_test >= threshold).sum())

    print()
    print(f"test macro-F1 = {f1_score(y[test_idx], pred_test, average='macro'):.4f}"
          f"  accuracy = {accuracy_score(y[test_idx], pred_test):.4f}")
    print(f"sight-threatening recall (thresholded) = {sight_recall:.4f}")
    print(f"any-DR recall (half threshold)        = {any_dr_recall:.4f}")
    print(f"referred at threshold                 = {flagged} of {len(test_idx)}")
    print()
    print(classification_report(
        y[test_idx], pred_test,
        target_names=[c[1] for c in CONDITIONS], digits=3))
    print(confusion_matrix(y[test_idx], pred_test))

    ART.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": best_model,
            "classes": [CODES[c] for c in range(5)],
            "concern_weight": CONCERN_WEIGHT,
            "referral_threshold": threshold,
        },
        ART / "dr_model.joblib",
        compress=3,
    )
    (ART / "dr_metrics.json").write_text(
        json.dumps(
            {
                "selected_model": best_name,
                "validation_macro_f1": {
                    name: round(
                        f1_score(
                            y[val_idx], m.predict(X[val_idx]), average="macro"
                        ),
                        4,
                    )
                    for name, m in candidates.items()
                },
                "test_macro_f1": round(
                    f1_score(y[test_idx], pred_test, average="macro"), 4
                ),
                "test_accuracy": round(
                    accuracy_score(y[test_idx], pred_test), 4
                ),
                "sight_threatening_recall": round(sight_recall, 4),
                "any_dr_recall": round(any_dr_recall, 4),
                "referral_threshold": threshold,
                "referred_of_test": f"{flagged}/{len(test_idx)}",
                "class_counts": {
                    CONDITIONS[c][1]: int((y == c).sum()) for c in range(5)
                },
                "seed": SEED,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nartifacts -> {ART}")


if __name__ == "__main__":
    main()
