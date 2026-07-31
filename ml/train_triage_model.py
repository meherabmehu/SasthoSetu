# -*- coding: utf-8 -*-
"""Train the BanglaMed triage severity classifier.

Compares candidate models on the validation split, selects the best by macro-F1,
calibrates it, and writes the artifact plus metrics consumed by the serving
layer and the model card.

Feature representation is a union of word n-grams and character n-grams. The
character features matter more than usual here: Bangla input arrives with
inconsistent spelling and romanisation, and char_wb n-grams degrade gracefully
where a word-level vocabulary would miss entirely.

Deterministic: seed 42.

Output:
    backend/app/ai/artifacts/triage_model.joblib
    backend/app/ai/artifacts/triage_metrics.json
    backend/app/ai/artifacts/triage_confusion.csv
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    recall_score,
)
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from sklearn.svm import LinearSVC

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.extraction import normalize  # noqa: E402
from app.ai.features import clinical_feature_matrix, text_column  # noqa: E402

SEED = 42
DATA = ROOT / "data" / "triage" / "symptom_triage_dataset.csv"
ART = ROOT / "backend" / "app" / "ai" / "artifacts"


def _tfidf(analyzer: str, ngram_range: tuple, min_df: int) -> Pipeline:
    """A TF-IDF branch that reads the text column out of the input frame."""
    return Pipeline(
        [
            ("select", FunctionTransformer(text_column)),
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer=analyzer,
                    ngram_range=ngram_range,
                    min_df=min_df,
                    sublinear_tf=True,
                    preprocessor=normalize,
                ),
            ),
        ]
    )


def _features() -> FeatureUnion:
    """Word n-grams + character n-grams + structured clinical signals."""
    return FeatureUnion(
        [
            ("word", _tfidf("word", (1, 2), 2)),
            ("char", _tfidf("char_wb", (2, 5), 3)),
            (
                "clinical",
                Pipeline(
                    [
                        ("build", FunctionTransformer(clinical_feature_matrix)),
                        ("scale", StandardScaler()),
                    ]
                ),
            ),
        ]
    )


CANDIDATES = {
    "logreg": LogisticRegression(
        max_iter=2000, C=4.0, class_weight="balanced", random_state=SEED
    ),
    "linearsvc": LinearSVC(C=0.5, class_weight="balanced", random_state=SEED),
    "random_forest": RandomForestClassifier(
        n_estimators=300,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=SEED,
        n_jobs=-1,
    ),
}


def main() -> None:
    if not DATA.exists():
        raise SystemExit(
            f"missing {DATA} - run ml/generate_triage_dataset.py first"
        )

    frame = pd.read_csv(DATA)
    train = frame[frame["split"] == "train"]
    val = frame[frame["split"] == "val"]
    test = frame[frame["split"] == "test"]

    columns = ["text", "age"]
    x_train, y_train = train[columns], train["triage_level"]
    x_val, y_val = val[columns], val["triage_level"]
    x_test, y_test = test[columns], test["triage_level"]

    print(f"train={len(train)} val={len(val)} test={len(test)}")

    scores = {}
    for name, estimator in CANDIDATES.items():
        pipeline = Pipeline([("features", _features()), ("clf", estimator)])
        pipeline.fit(x_train, y_train)
        predicted = pipeline.predict(x_val)
        score = f1_score(y_val, predicted, average="macro")
        scores[name] = round(float(score), 4)
        print(f"  {name:14} val macro-F1 = {score:.4f}")

    best_name = max(scores, key=scores.get)
    print(f"selected: {best_name}")

    # Refit the winner on train+val, then calibrate so the served confidence
    # score is meaningful rather than an uncalibrated margin.
    x_full = pd.concat([x_train, x_val])
    y_full = pd.concat([y_train, y_val])

    base = Pipeline([("features", _features()), ("clf", CANDIDATES[best_name])])
    method = "sigmoid" if best_name == "linearsvc" else "isotonic"
    model = CalibratedClassifierCV(base, method=method, cv=3)
    model.fit(x_full, y_full)

    predicted = model.predict(x_test)
    macro_f1 = f1_score(y_test, predicted, average="macro")
    accuracy = accuracy_score(y_test, predicted)

    level5_recall = recall_score(
        y_test, predicted, labels=[5], average="macro", zero_division=0
    )

    matrix = confusion_matrix(y_test, predicted, labels=[1, 2, 3, 4, 5])

    # A level-1 case predicted as level-5 (or the reverse) is a different class
    # of error from an adjacent-band disagreement; report it explicitly.
    severe_errors = int(
        sum(
            matrix[i][j]
            for i in range(5)
            for j in range(5)
            if abs(i - j) >= 3
        )
    )
    under_triage = int(
        sum(matrix[i][j] for i in range(5) for j in range(5) if j < i)
    )

    print(f"\ntest macro-F1 = {macro_f1:.4f}  accuracy = {accuracy:.4f}")
    print(f"level-5 recall = {level5_recall:.4f}")
    print(f"severe (>=3 band) errors = {severe_errors}")
    print("\n" + classification_report(y_test, predicted, zero_division=0))

    ART.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, ART / "triage_model.joblib")

    metrics = {
        "selected_model": best_name,
        "validation_macro_f1": scores,
        "test_macro_f1": round(float(macro_f1), 4),
        "test_accuracy": round(float(accuracy), 4),
        "level5_recall": round(float(level5_recall), 4),
        "severe_band_errors": severe_errors,
        "under_triage_count": under_triage,
        "test_size": int(len(test)),
        "labels": [1, 2, 3, 4, 5],
        "seed": SEED,
    }
    (ART / "triage_metrics.json").write_text(json.dumps(metrics, indent=2))

    pd.DataFrame(
        matrix,
        index=[f"true_{i}" for i in range(1, 6)],
        columns=[f"pred_{i}" for i in range(1, 6)],
    ).to_csv(ART / "triage_confusion.csv")

    print(f"\nartifacts -> {ART}")


if __name__ == "__main__":
    main()
