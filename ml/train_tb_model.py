# -*- coding: utf-8 -*-
"""Train the tuberculosis screen on the combined chest-film collection.

Fifteen thousand films over four classes - tuberculosis, pneumonia,
COVID-19, normal - using the same 32 handcrafted features as the other
film model. The question the screen answers is not "which of four" but
"does this film need a TB workup": a summed concern score weighted toward
tuberculosis, compared against a threshold chosen on validation for a high
TB recall. A missed TB film means weeks of continued transmission before
symptoms force a visit; an over-referred clear film costs one sputum test.

Output: backend/app/ai/artifacts/tb_model.joblib, tb_metrics.json

    python ml/train_tb_model.py
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
IMAGES = IMAGING / "tb"
LABELS = IMAGING / "tb_labels.csv"
ART = Path(os.environ.get("SASTHOSETU_ARTIFACT_DIR", ROOT / "backend" / "app" / "ai" / "artifacts"))

from imaging_training import features_for_rows, make_split, recall_threshold

SEED = 42

CONDITIONS = [
    (0, "Tuberculosis", "যক্ষ্মা (টিবি) সন্দেহ"),
    (1, "Pneumonia", "নিউমোনিয়া"),
    (2, "COVID-19", "কোভিড-১৯ সন্দেহ"),
    (3, "Normal", "স্বাভাবিক"),
]
CODES = {0: "tuberculosis", 1: "pneumonia", 2: "covid19", 3: "normal"}

# Tuberculosis carries the referral weight - confirmation needs a sputum
# test and untreated TB keeps transmitting. COVID sits just behind it for
# the same isolation reason. Pneumonia is already screened by a dedicated
# model, so here it carries only a token weight.
CONCERN_WEIGHT = {0: 1.0, 1: 0.2, 2: 0.7, 3: 0.0}


def load_rows() -> list[dict]:
    with LABELS.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def features_for(rows: list[dict]):
    return features_for_rows(rows, IMAGES, "tb")

def concern_score(proba: np.ndarray) -> np.ndarray:
    return sum(w * proba[:, c] for c, w in CONCERN_WEIGHT.items())


def main() -> None:
    print("Extracting film features")
    rows = load_rows()
    X, y = features_for(rows)
    print(f"  {len(rows)} films, {X.shape[1]} features each")

    train_idx, val_idx, test_idx = make_split(rows, IMAGES, "tb", ART, group_field='patient_id', fraction=0.15)
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
    is_tb_val = y[val_idx] == 0

    threshold = recall_threshold(scores_val, is_tb_val, target=0.90)
    print(
        f"referral threshold = {threshold:.2f} "
        f"(validation, >=90% tuberculosis recall)"
    )

    proba_test = best_model.predict_proba(X[test_idx])
    scores_test = concern_score(proba_test)
    pred_test = best_model.predict(X[test_idx])

    tb_recall = recall_score(y[test_idx] == 0, scores_test >= threshold)
    flagged = int((scores_test >= threshold).sum())

    print()
    print(f"test macro-F1 = {f1_score(y[test_idx], pred_test, average='macro'):.4f}"
          f"  accuracy = {accuracy_score(y[test_idx], pred_test):.4f}")
    print(f"tuberculosis recall (thresholded) = {tb_recall:.4f}")
    print(f"referred at threshold            = {flagged} of {len(test_idx)}")
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
        ART / "tb_model.joblib",
        compress=3,
    )
    (ART / "tb_metrics.json").write_text(
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
                "tuberculosis_recall": round(tb_recall, 4),
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
