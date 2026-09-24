# -*- coding: utf-8 -*-
"""Regenerate every dataset and trained model artifact in one command.

    python ml/prepare_all.py          (from the repo root, ~2-3 min on CPU)

Everything is deterministic (seed 42): the generated CSVs and trained
joblib artifacts are byte-stable given the same library versions, which is
why the large generated files are not committed - this script is the source
of truth. CI runs it before the test suite.

Produces:
    data/real/{nhamcs_ed_triage,bd_health_facilities,bd_dengue_*}.csv
    data/seed/{hospitals,pharmacies,laboratories,doctors}.json
    data/drugs/{bd_brand_aliases,drug_interactions}.csv
    data/triage/symptom_triage_dataset.csv   (generated + real presentations)
    data/real/skin/metadata.csv              (HAM10000 labels)
    data/surge/{bed_utilization,surge_events}.csv
    data/surveillance/{weekly_surveillance,injected_outbreaks}.csv
    backend/app/ai/artifacts/{triage_model.joblib, triage_metrics.json,
                              triage_confusion.csv, surge_model.joblib,
                              surge_metrics.json, skin_model.joblib,
                              skin_metrics.json}
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runtime import configure_worker_cpus  # noqa: E402

ML = Path(__file__).resolve().parent

STEPS = [
    ("Real data (ED visits, facilities, dengue, Bangla symptoms)",
     "fetch_real_data.py"),
    ("Facility seed from real coordinates", "build_facility_seed.py"),
    ("Seed data (doctors)", "generate_seed.py"),
    ("Drug knowledge base (brands + interactions)", "generate_drug_kb.py"),
    ("Bangla notes from real ED presentations", "build_bangla_from_real.py"),
    ("Triage corpus (generated + real presentations)",
     "build_triage_corpus.py"),
    ("Bed utilization logs (2 years x 5 hospitals)", "generate_bed_logs.py"),
    ("Surveillance corpus (12 districts x 8 diseases)",
     "generate_surveillance.py"),
    ("Train triage classifier", "train_triage_model.py"),
    ("Train surge forecaster", "train_surge_model.py"),
]

# The skin model needs 2.8 GB of dermatoscopic images, which is a long download
# and a non-commercial licence. It is offered rather than forced: without it
# the rest of the platform works and the skin page reports itself unavailable.
OPTIONAL = [
    ("Medical imaging datasets (DermNet + chest X-ray, ~1.7 GB)",
     "fetch_medical_datasets.py"),
    ("Viral rash photographs (MSID, 54 MB)", "fetch_mpox_data.py"),
    ("Train skin condition classifier (23 conditions)",
     "train_dermnet_model.py"),
    ("Pigmented lesion images (HAM10000, ~2.8 GB)", "fetch_skin_data.py"),
    ("Train pigmented lesion classifier", "train_skin_model.py"),
    ("Train chest X-ray pneumonia screen", "train_chest_xray_model.py"),
    ("Train viral rash screen", "train_mpox_model.py"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-skin", action="store_true",
        help="also download the imaging datasets and train the image models",
    )
    parser.add_argument(
        "--skip-download", action="store_true",
        help="use whatever is already cached instead of fetching",
    )
    args = parser.parse_args()

    steps = list(STEPS)
    if args.skip_download:
        steps = [s for s in steps if s[1] != "fetch_real_data.py"]
    if args.with_skin:
        steps = steps + OPTIONAL

    configure_worker_cpus()
    env = dict(os.environ)

    t0 = time.time()
    for label, script in steps:
        print(f"\n=== {label} -> {script}")
        subprocess.run([sys.executable, str(ML / script)], check=True, env=env)

    print(f"\nAll datasets and artifacts ready in {time.time() - t0:.0f}s.")
    if not args.with_skin:
        print("Image models not built. Add --with-skin to include them "
              "(downloads about 4.5 GB).")


if __name__ == "__main__":
    main()
