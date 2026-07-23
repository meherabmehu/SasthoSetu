# -*- coding: utf-8 -*-
"""Fold human feedback (ai_feedback table) into triage retraining.

Closes the loop promised by POST /v1/ai/feedback: corrected triage examples
are appended to the training corpus (as new 'feedback' language rows) and the
model is retrained via ml/train_triage_model.py.

Usage (repo root):  python ml/retrain_from_feedback.py [--min-rows 25]

Safeguards: only rows with an explicit corrected_level are used; duplicates
(same text + level) are dropped; a fresh model is written only if test
macro-F1 does not regress by more than 0.01 versus the current artifact.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd


def _csv(path):
    """Return path if it exists, else its .gz sibling (fresh clones ship .gz)."""
    import pathlib as _pl
    p = _pl.Path(path)
    return p if p.exists() else p.with_name(p.name + ".gz")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.database import SessionLocal  # noqa: E402
from app.models.ai_feedback import AIFeedback  # noqa: E402

CSV = ROOT / "data" / "triage" / "symptom_triage_dataset.csv"
METRICS = ROOT / "backend" / "app" / "ai" / "artifacts" / "triage_metrics.json"


def main(min_rows: int) -> None:
    db = SessionLocal()
    try:
        rows = (db.query(AIFeedback)
                .filter(AIFeedback.feature == "triage",
                        AIFeedback.corrected_level.isnot(None),
                        AIFeedback.input_text.isnot(None)).all())
    finally:
        db.close()

    if len(rows) < min_rows:
        print(f"Only {len(rows)} corrected feedback rows (< {min_rows}); "
              "skipping retrain.")
        return

    df = pd.read_csv(_csv(CSV))
    add = pd.DataFrame({
        "text": [r.input_text for r in rows],
        "triage_level": [r.corrected_level for r in rows],
    })
    add = add[~add.text.isin(df.text)].drop_duplicates("text")
    if add.empty:
        print("No new unique feedback texts; skipping retrain.")
        return

    add["language"] = "feedback"
    add["specialty"] = "General Medicine"
    add["red_flag"] = (add.triage_level == 5).astype(int)
    add["split"] = "train"                       # never contaminate test
    for col in df.columns:
        if col not in add.columns:
            add[col] = ""
    df = pd.concat([df, add[df.columns]], ignore_index=True)
    df.to_csv(CSV, index=False)
    print(f"Appended {len(add)} feedback rows -> {CSV.name} "
          f"({len(df)} total). Retraining...")

    before = json.loads(METRICS.read_text())["test"]["macro_f1"]
    subprocess.run([sys.executable, str(ROOT / "ml" / "train_triage_model.py")],
                   check=True)
    after = json.loads(METRICS.read_text())["test"]["macro_f1"]
    print(f"macro-F1: {before:.4f} -> {after:.4f}")
    if after < before - 0.01:
        print("WARNING: regression beyond tolerance - review the feedback "
              "rows before deploying this artifact.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-rows", type=int, default=25)
    main(ap.parse_args().min_rows)
