# -*- coding: utf-8 -*-
"""Train the smartphone lesion screen on PAD-UFES-20.

Six classes over 2,298 smartphone photographs, same 32 handcrafted features
as every other image model. The referral question is the familiar one:
does this photograph show something that needs a dermatologist? A summed
concern score across the malignant and precancerous classes, compared to a
threshold chosen on validation for a high malignant recall.

Why this model exists alongside the HAM10000 one: that model reads
dermatoscope images; this one reads phone photographs, which is what our
users actually submit. Two screens, each closer to one kind of input, and
neither can lower what the other raised.

Output: backend/app/ai/artifacts/pad_model.joblib, pad_metrics.json

    python ml/train_pad_model.py
"""
from __future__ import annotations

import csv
import os
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, ExtraTreesClassifier
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


IMAGING = ROOT / "data" / "real" / "imaging"
IMAGES = IMAGING / "pad"
LABELS = IMAGING / "pad_labels.csv"
ART = Path(os.environ.get("SASTHOSETU_ARTIFACT_DIR", ROOT / "backend" / "app" / "ai" / "artifacts"))

from imaging_training import features_for_rows, make_split, recall_threshold

SEED = 42

CONDITIONS = [
    (0, "BCC", "বেসাল সেল কার্সিনোমা"),
    (1, "SCC", "স্কোয়ামাস সেল কার্সিনোমা"),
    (2, "MEL", "মেলানোমা"),
    (3, "ACK", "অ্যাক্টিনিক কেরাটোসিস"),
    (4, "NEV", "সাধারণ তিল"),
    (5, "SEK", "সেবোরিক কেরাটোসিস"),
]
CODES = {0: "bcc", 1: "scc", 2: "mel", 3: "ack", 4: "nev", 5: "sek"}

# Malignant classes carry the full referral weight; actinic keratosis is
# precancerous and carries most of it.
CONCERN_WEIGHT = {0: 1.0, 1: 1.0, 2: 1.0, 3: 0.7, 4: 0.0, 5: 0.0}


def load_rows() -> list[dict]:
    with LABELS.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def features_for(rows: list[dict]):
    return features_for_rows(rows, IMAGES, "pad")

def concern_score(proba: np.ndarray) -> np.ndarray:
    return sum(w * proba[:, c] for c, w in CONCERN_WEIGHT.items())


def main() -> None:
    print("Extracting image features")
    rows = load_rows()
    X, y = features_for(rows)
    print(f"  {len(rows)} images, {X.shape[1]} features each")

    train_idx, val_idx, test_idx = make_split(rows, IMAGES, "pad", ART, group_field='patient_id', fraction=0.15)
    print(f"train={len(train_idx)} val={len(val_idx)} test={len(test_idx)}")

    candidates = {
        "extra_trees_balanced": ExtraTreesClassifier(
            n_estimators=400, min_samples_leaf=2, class_weight="balanced",
            n_jobs=2, random_state=SEED),
        "hist_gradient_boosting_balanced": HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.05, class_weight="balanced", random_state=SEED),
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
    malignant_val = np.isin(y[val_idx], [0, 1, 2])

    threshold = recall_threshold(scores_val, malignant_val, target=0.90)
    print(
        f"referral threshold = {threshold:.2f} "
        f"(validation, >=90% malignant recall)"
    )

    proba_test = best_model.predict_proba(X[test_idx])
    scores_test = concern_score(proba_test)
    pred_test = best_model.predict(X[test_idx])

    malignant_recall = recall_score(
        np.isin(y[test_idx], [0, 1, 2]), scores_test >= threshold
    )
    flagged = int((scores_test >= threshold).sum())

    print()
    print(f"test macro-F1 = {f1_score(y[test_idx], pred_test, average='macro'):.4f}"
          f"  accuracy = {accuracy_score(y[test_idx], pred_test):.4f}")
    print(f"malignant recall (thresholded) = {malignant_recall:.4f}")
    print(f"referred at threshold         = {flagged} of {len(test_idx)}")
    print()
    print(classification_report(
        y[test_idx], pred_test,
        target_names=[c[1] for c in CONDITIONS], digits=3))
    print(confusion_matrix(y[test_idx], pred_test))

    ART.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": best_model,
            "classes": [CODES[c] for c in range(6)],
            "concern_weight": CONCERN_WEIGHT,
            "referral_threshold": threshold,
        },
        ART / "pad_model.joblib",
        compress=3,
    )
    (ART / "pad_metrics.json").write_text(
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
                "malignant_recall": round(malignant_recall, 4),
                "referral_threshold": threshold,
                "referred_of_test": f"{flagged}/{len(test_idx)}",
                "class_counts": {
                    CONDITIONS[c][1]: int((y == c).sum()) for c in range(6)
                },
                "seed": SEED,
                "evaluation_protocol": "source_groups_and_pixel_phash_components_v1",
                "clinically_validated": False,
                "split_strategy": "patient_and_pixel_phash_components",
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
