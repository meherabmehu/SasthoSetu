# -*- coding: utf-8 -*-
"""Train the viral-rash screen on the MSID photographs.

Four confusable classes - monkeypox, chickenpox, measles, normal skin - over
770 photographs. The features are the same 32 handcrafted ABCD-rule
measurements the other skin models use, and the decision the model serves is
the same referral question: does this photograph need a doctor, today?

The safety asymmetry mirrors the other image models. Dismissing a monkeypox
photograph as normal is a public-health failure - isolation and contact
tracing lose their window - while referring a chickenpox is an
inconvenience. The referral decision therefore sums the probability across
the concerning classes (monkeypox always; chickenpox and measles at a lower
weight, since a doctor confirming them matters but not within the day) and
compares it to a threshold chosen on the validation split for a high
monkeypox recall.

Output: backend/app/ai/artifacts/mpox_model.joblib, mpox_metrics.json

    python ml/train_mpox_model.py
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
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


IMAGING = ROOT / "data" / "real" / "imaging"
IMAGES = IMAGING / "mpox"
LABELS = IMAGING / "mpox_labels.csv"
ART = Path(os.environ.get("SASTHOSETU_ARTIFACT_DIR", ROOT / "backend" / "app" / "ai" / "artifacts"))

from imaging_training import features_for_rows, make_split, recall_threshold

SEED = 42

CONDITIONS = [
    (0, "Monkeypox", "মাংকিপক্স সন্দেহ"),
    (1, "Chickenpox", "জলবসন্ত (চিকেনপক্স)"),
    (2, "Measles", "হাম"),
    (3, "Normal", "স্বাভাবিক ত্বক"),
]
CODES = {0: "mpox", 1: "chickenpox", 2: "measles", 3: "normal"}

# The classes a doctor must see promptly. Monkeypox carries the whole
# weight; the two other viral rashes are grouped at a lower weight because
# confirmation matters but same-day urgency does not.
CONCERN_WEIGHT = {0: 1.0, 1: 0.3, 2: 0.3, 3: 0.0}


def load_rows() -> list[dict]:
    with LABELS.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def features_for(rows: list[dict]):
    return features_for_rows(rows, IMAGES, "mpox")

def concern_score(proba: np.ndarray) -> np.ndarray:
    return sum(w * proba[:, c] for c, w in CONCERN_WEIGHT.items())


def main() -> None:
    print("Extracting image features")
    rows = load_rows()
    X, y = features_for(rows)
    print(f"  {len(rows)} images, {X.shape[1]} features each")

    train_idx, val_idx, test_idx = make_split(rows, IMAGES, "mpox", ART, group_field=None, fraction=0.2)
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

    best_name, best_model, best_f1 = None, None, -1.0
    for model in candidates.values():
        model.fit(X[train_idx], y[train_idx])
    for name, model in candidates.items():
        val_f1 = f1_score(
            y[val_idx], model.predict(X[val_idx]), average="macro"
        )
        print(f"  {name:24} val macro-F1 = {val_f1:.4f}")
        if val_f1 > best_f1:
            best_name, best_model, best_f1 = name, model, val_f1
    print(f"selected: {best_name}")

    # Referral threshold: the lowest concern score on validation whose
    # monkeypox recall stays >= 90%.
    proba_val = best_model.predict_proba(X[val_idx])
    scores_val = concern_score(proba_val)
    is_mpox_val = y[val_idx] == 0

    threshold = recall_threshold(scores_val, is_mpox_val, target=0.90)
    print(
        f"referral threshold = {threshold:.2f} "
        f"(validation, >=90% monkeypox recall)"
    )

    proba_test = best_model.predict_proba(X[test_idx])
    scores_test = concern_score(proba_test)
    pred_test = best_model.predict(X[test_idx])

    mpox_recall = recall_score(y[test_idx] == 0, scores_test >= threshold)
    flagged = int((scores_test >= threshold).sum())

    print()
    print(f"test macro-F1 = {f1_score(y[test_idx], pred_test, average='macro'):.4f}"
          f"  accuracy = {accuracy_score(y[test_idx], pred_test):.4f}")
    print(f"monkeypox recall (thresholded) = {mpox_recall:.4f}")
    print(f"referred at threshold          = {flagged} of {len(test_idx)}")
    print()
    print(classification_report(
        y[test_idx], pred_test,
        target_names=[c[1] for c in CONDITIONS], digits=3))
    print(confusion_matrix(y[test_idx], pred_test))

    ART.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": best_model,
            "classes": [CODES[c] for c in range(4)],
            "concern_weight": CONCERN_WEIGHT,
            "referral_threshold": threshold,
        },
        ART / "mpox_model.joblib",
        compress=3,
    )
    (ART / "mpox_metrics.json").write_text(
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
                "monkeypox_recall": round(mpox_recall, 4),
                "referral_threshold": threshold,
                "referred_of_test": f"{flagged}/{len(test_idx)}",
                "class_counts": {
                    CONDITIONS[c][1]: int((y == c).sum()) for c in range(4)
                },
                "seed": SEED,
                "evaluation_protocol": "source_groups_and_pixel_phash_components_v1",
                "clinically_validated": False,
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
