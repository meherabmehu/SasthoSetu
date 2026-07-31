# -*- coding: utf-8 -*-
"""Regenerate every dataset and trained model artifact in one command.

    python ml/prepare_all.py          (from the repo root, ~2-3 min on CPU)

Everything is deterministic (seed 42): the generated CSVs and trained
joblib artifacts are byte-stable given the same library versions, which is
why the large generated files are not committed - this script is the source
of truth. CI runs it before the test suite.

Produces:
    data/seed/{hospitals,doctors}.json
    data/drugs/{bd_brand_aliases,drug_interactions}.csv
    data/triage/symptom_triage_dataset.csv   (9,000 rows)
    data/surge/{bed_utilization,surge_events}.csv
    data/surveillance/{weekly_surveillance,injected_outbreaks}.csv
    backend/app/ai/artifacts/{triage_model.joblib, triage_metrics.json,
                              triage_confusion.csv, surge_model.joblib,
                              surge_metrics.json}
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ML = Path(__file__).resolve().parent

STEPS = [
    ("Seed data (hospitals + doctors)", "generate_seed.py"),
    ("Drug knowledge base (brands + interactions)", "generate_drug_kb.py"),
    ("Triage corpus (9,000 rows)", "generate_triage_dataset.py"),
    ("Bed utilization logs (2 years x 5 hospitals)", "generate_bed_logs.py"),
    ("Surveillance corpus (12 districts x 8 diseases)",
     "generate_surveillance.py"),
    ("Train triage classifier", "train_triage_model.py"),
    ("Train surge forecaster", "train_surge_model.py"),
]


def main() -> None:
    t0 = time.time()
    for label, script in STEPS:
        print(f"\n=== {label} -> {script}")
        subprocess.run([sys.executable, str(ML / script)], check=True)
    print(f"\nAll datasets and artifacts ready in {time.time() - t0:.0f}s.")


if __name__ == "__main__":
    main()
