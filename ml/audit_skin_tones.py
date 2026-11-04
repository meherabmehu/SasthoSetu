"""Audit PAD referral outcomes by Fitzpatrick type on the frozen test set only.

Missing types/positive cases remain visible as unmeasured, never perfect recall.
Run after evaluate_imaging.py pad; no training images enter this report.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from evaluate_imaging import binary_metrics, grouped_intervals

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "backend/app/ai/artifacts"
TONE_NAMES = {"1": "I — সবচেয়ে ফর্সা", "2": "II — ফর্সা", "3": "III — গমবর্ণ",
              "4": "IV — বাদামি", "5": "V — গাঢ় বাদামি", "6": "VI — কালো"}


def audit(artifacts=ART, report_path=ROOT / "docs/model_cards/skin_tone_audit.md"):
    artifacts = Path(artifacts)
    with (ROOT / "data/real/imaging/pad_labels.csv").open(encoding="utf-8") as handle:
        labels = {row["file"]: row for row in csv.DictReader(handle)}
    with (artifacts / "pad_holdout_predictions.csv").open(encoding="utf-8") as handle:
        predictions = list(csv.DictReader(handle))
    holdout = json.loads((artifacts / "pad_holdout.json").read_text(encoding="utf-8"))
    if hashlib.sha256((artifacts / "pad_model.joblib").read_bytes()).hexdigest() != holdout["model_sha256"]:
        raise ValueError("Model changed after holdout evaluation")
    with (artifacts / "pad_evaluation.csv").open(encoding="utf-8") as handle:
        test_files = {row["file"] for row in csv.DictReader(handle) if row["partition"] == "test"}
    if {row["file"] for row in predictions} != test_files:
        raise ValueError("Predictions must cover exactly the frozen test partition")
    tones = {}
    for tone in TONE_NAMES:
        samples = [row for row in predictions if labels[row["file"]]["fitspatrick"].strip() == tone]
        if not samples:
            tones[tone] = {"n": 0, "positive_images": 0, "recall": None, "specificity": None,
                           "referred_fraction": None, "confidence_intervals": None}
            continue
        truth = np.array([row["positive"] == "True" for row in samples])
        flagged = np.array([row["referred"] == "True" for row in samples])
        tones[tone] = {"n": len(samples), "positive_images": int(truth.sum()),
                       **binary_metrics(truth, flagged),
                       "confidence_intervals": grouped_intervals(
                           truth, flagged, np.array([row["component"] for row in samples]))}
    unlabelled = sum(not labels[row["file"]]["fitspatrick"].strip() for row in predictions)
    result = {"dataset": "PAD-UFES-20 frozen patient/component-disjoint test subset",
              "model_sha256": holdout["model_sha256"], "clinically_validated": False,
              "test_images": len(predictions), "unlabelled_tone_images": unlabelled, "tones": tones}
    (artifacts / "skin_tone_audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    def percentage(value):
        return "unmeasured" if value is None else f"{value:.1%}"

    lines = ["# Skin-tone audit — held-out smartphone photographs", "",
        "Only PAD's frozen test partition is included. Patient IDs and duplicate components are disjoint "
        "from training and validation. The model and referral threshold were fixed before this audit.", "",
        "রেফার হার and malignant recall are reported separately. Positive labels are BCC, SCC and MEL; "
        "the referral score also weights precancerous ACK. These are retrospective research results, "
        "not clinical validation or evidence of performance on Bangladeshi patients.", "",
        "| Fitzpatrick type | Test images | Malignant images | Referral rate | Malignant recall | Specificity |",
        "|---|---:|---:|---:|---:|---:|"]
    for tone, data in tones.items():
        lines.append(f"| {TONE_NAMES[tone]} | {data['n']} | {data['positive_images']} | "
                     f"{percentage(data['referred_fraction'])} | {percentage(data['recall'])} | "
                     f"{percentage(data['specificity'])} |")
    lines += ["", f"{unlabelled} test images lack a Fitzpatrick label and are omitted from tone comparisons.",
        "", "Zero positive cases means recall is unmeasured. Small groups cannot establish parity; "
        "the companion JSON reports 95% component-bootstrap intervals (1,000 repetitions), "
        "which remain unreliable for very small groups. Fitzpatrick type is a limited proxy, not ethnicity.",
        "", "Independent consented Bangladeshi cohorts, especially darker skin types, and clinician review "
        "are still required. No fairness claim follows from these results.", "",
        "Source: [PAD-UFES-20, CC BY 4.0](https://data.mendeley.com/datasets/zr7vgbcyr2/1).", "",
        "Reproduce: `python ml/audit_skin_tones.py` after `python ml/evaluate_imaging.py pad --artifacts "
        "backend/app/ai/artifacts`.", ""]
    Path(report_path).write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=ART)
    parser.add_argument("--report", type=Path, default=ROOT / "docs/model_cards/skin_tone_audit.md")
    args = parser.parse_args()
    audit(args.artifacts, args.report)
