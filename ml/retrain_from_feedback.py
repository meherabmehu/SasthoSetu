# -*- coding: utf-8 -*-
"""Fold clinician feedback back into the triage model.

Closes the learning loop. Two sources are used, both of which represent a
human correcting the model:

* ``triage_sessions`` rows a clinician reviewed and overrode, which carry the
  original patient wording alongside the corrected severity.
* ``ai_feedback`` rows submitted through ``POST /api/v1/ai/feedback``.

Usage (from the repository root):

    python ml/retrain_from_feedback.py [--min-rows 25] [--dry-run]

Safeguards, in order of importance:

1. Corrections only ever enter the **training** split. Letting them reach the
   test split would let the model be judged on the very examples it was just
   handed, and the reported score would stop meaning anything.
2. The retrained artifact is written to a temporary location and only promoted
   if it does not regress. A feedback batch that makes triage worse must not
   reach patients simply because it was the most recent run.
3. Emergency recall is gated separately and more tightly than overall accuracy,
   because missing a red flag is not the same kind of error as mislabelling a
   mild case.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.database import SessionLocal  # noqa: E402
from app.models.ai_feedback import AIFeedback  # noqa: E402
from app.models.triage_session import TriageSession  # noqa: E402

CSV = ROOT / "data" / "triage" / "symptom_triage_dataset.csv"
ARTIFACTS = ROOT / "backend" / "app" / "ai" / "artifacts"
METRICS = ARTIFACTS / "triage_metrics.json"
MODEL = ARTIFACTS / "triage_model.joblib"

# A retrain may lose this much overall macro-F1 before it is rejected.
MACRO_F1_TOLERANCE = 0.01
# Emergency recall may not fall at all: under-triaging a red flag is the one
# failure mode with irreversible consequences.
LEVEL5_RECALL_TOLERANCE = 0.0


def collect_corrections(min_rows: int) -> pd.DataFrame:
    """Gather every human correction available, de-duplicated by text."""
    db = SessionLocal()
    try:
        reviewed = (
            db.query(TriageSession)
            .filter(
                TriageSession.clinician_level.isnot(None),
                TriageSession.input_text.isnot(None),
            )
            .all()
        )
        submitted = (
            db.query(AIFeedback)
            .filter(
                AIFeedback.feature == "triage",
                AIFeedback.corrected_level.isnot(None),
                AIFeedback.input_text.isnot(None),
            )
            .all()
        )
    finally:
        db.close()

    records = [
        {
            "text": row.input_text,
            "triage_level": int(row.clinician_level),
            "age": row.age_years if row.age_years is not None else "",
            "source": "clinician_review",
        }
        for row in reviewed
    ] + [
        {
            "text": row.input_text,
            "triage_level": int(row.corrected_level),
            "age": "",
            "source": "ai_feedback",
        }
        for row in submitted
    ]

    frame = pd.DataFrame(records)
    if frame.empty:
        return frame

    frame = frame[frame["triage_level"].between(1, 5)]
    return frame.drop_duplicates(subset="text", keep="last")


def read_metrics() -> dict:
    if not METRICS.exists():
        return {}
    return json.loads(METRICS.read_text())


def _restore(corpus_backup: Path, model_backup: Path) -> None:
    """Put the previous corpus and model back, leaving no stray files."""
    if corpus_backup.exists():
        shutil.copy2(corpus_backup, CSV)
    if model_backup.exists():
        shutil.copy2(model_backup, MODEL)
    _discard(corpus_backup, model_backup)


def _discard(corpus_backup: Path, model_backup: Path) -> None:
    corpus_backup.unlink(missing_ok=True)
    model_backup.unlink(missing_ok=True)


def main(min_rows: int, dry_run: bool) -> None:
    if not CSV.exists():
        raise SystemExit(
            f"missing {CSV} - run ml/generate_triage_dataset.py first"
        )

    corrections = collect_corrections(min_rows)
    if corrections.empty:
        print("No clinician corrections recorded yet; nothing to retrain on.")
        return

    corpus = pd.read_csv(CSV)
    fresh = corrections[~corrections["text"].isin(corpus["text"])]

    if len(fresh) < min_rows:
        print(
            f"Only {len(fresh)} new corrections available "
            f"(threshold {min_rows}); skipping retrain."
        )
        return

    print(f"{len(fresh)} new corrections:")
    print(fresh["source"].value_counts().to_string())
    print(fresh["triage_level"].value_counts().sort_index().to_string())

    if dry_run:
        print("\nDry run: corpus and artifacts left untouched.")
        return

    baseline = read_metrics()
    corpus_backup = CSV.with_suffix(".csv.bak")
    model_backup = MODEL.with_suffix(".joblib.bak")
    shutil.copy2(CSV, corpus_backup)
    if MODEL.exists():
        shutil.copy2(MODEL, model_backup)

    additions = pd.DataFrame(
        {
            "text": fresh["text"],
            "language": "clinician",
            "symptoms": "",
            "duration_days": "",
            "qualifier": "",
            "age": fresh["age"],
            "triage_level": fresh["triage_level"],
            # Corrections train the model; they never grade it.
            "split": "train",
        }
    )

    combined = pd.concat([corpus, additions[corpus.columns]], ignore_index=True)
    combined.to_csv(CSV, index=False)
    print(f"\nCorpus grew from {len(corpus)} to {len(combined)} rows. Retraining...")

    try:
        subprocess.run(
            [sys.executable, str(ROOT / "ml" / "train_triage_model.py")],
            check=True,
        )
    except subprocess.CalledProcessError:
        _restore(corpus_backup, model_backup)
        raise SystemExit("Training failed; corpus and model restored.")

    updated = read_metrics()

    before_f1 = baseline.get("test_macro_f1", 0.0)
    after_f1 = updated.get("test_macro_f1", 0.0)
    before_recall = baseline.get("level5_recall", 0.0)
    after_recall = updated.get("level5_recall", 0.0)

    print(f"\nmacro-F1       {before_f1:.4f} -> {after_f1:.4f}")
    print(f"L5 recall      {before_recall:.4f} -> {after_recall:.4f}")

    rejected = []
    if after_f1 < before_f1 - MACRO_F1_TOLERANCE:
        rejected.append(
            f"macro-F1 fell by more than {MACRO_F1_TOLERANCE}"
        )
    if after_recall < before_recall - LEVEL5_RECALL_TOLERANCE:
        rejected.append("emergency recall regressed")

    if rejected:
        _restore(corpus_backup, model_backup)
        print("\nREJECTED: " + "; ".join(rejected))
        print("Corpus and previous model restored. Review the corrections "
              "before retrying.")
        raise SystemExit(1)

    _discard(corpus_backup, model_backup)
    print("\nAccepted: new model promoted.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-rows", type=int, default=25)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be used without touching the corpus",
    )
    arguments = parser.parse_args()
    main(arguments.min_rows, arguments.dry_run)
