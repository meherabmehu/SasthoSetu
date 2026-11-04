"""Evaluate frozen candidate artifacts on their recorded grouped holdout.

Selection and referral calibration happen on validation only. Confidence
intervals resample independent split components, not correlated photographs.
This is research evaluation, not prospective clinical validation.
"""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import sklearn
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.artifact_loading import load_artifact
from imaging_training import _signature, features_for_rows


def dataset_rows(name):
    if name == "skin":
        label_file = ROOT / "data/real/skin/metadata.csv"
        image_dir = ROOT / "data/real/skin/images"
    else:
        label_file = ROOT / f"data/real/imaging/{name}_labels.csv"
        image_dir = ROOT / f"data/real/imaging/{name}"
    with label_file.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if name == "skin":
        rows = [dict(row, file=f"{row['image_id']}.jpg") for row in rows
                if (image_dir / f"{row['image_id']}.jpg").exists()]
    return rows, image_dir, label_file


def _ratio(numerator, denominator):
    return float(numerator / denominator) if denominator else None


def binary_metrics(truth, flagged):
    tp, fp = int((truth & flagged).sum()), int((~truth & flagged).sum())
    tn, fn = int((~truth & ~flagged).sum()), int((truth & ~flagged).sum())
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "recall": _ratio(tp, tp + fn), "specificity": _ratio(tn, tn + fp),
            "precision": _ratio(tp, tp + fp), "referred_fraction": float(flagged.mean())}


def grouped_intervals(truth, flagged, components, repetitions=1000):
    unique = sorted(set(components))
    totals = np.array([[int((truth[components == group] & flagged[components == group]).sum()),
                        int((~truth[components == group] & flagged[components == group]).sum()),
                        int((~truth[components == group] & ~flagged[components == group]).sum()),
                        int((truth[components == group] & ~flagged[components == group]).sum())]
                       for group in unique])
    rng = np.random.default_rng(42)
    recall, specificity = [], []
    for _ in range(repetitions):
        tp, fp, tn, fn = totals[rng.integers(0, len(unique), len(unique))].sum(axis=0)
        if tp + fn:
            recall.append(tp / (tp + fn))
        if tn + fp:
            specificity.append(tn / (tn + fp))
    return {"method": "component_bootstrap_percentile", "repetitions": repetitions,
            "components": len(unique), "recall_95": np.quantile(recall, [0.025, 0.975]).tolist()
            if recall else None, "specificity_95": np.quantile(specificity, [0.025, 0.975]).tolist()
            if specificity else None}


def evaluate(name, artifacts):
    artifacts = Path(artifacts)
    model_file = artifacts / f"{name}_model.joblib"
    bundle = load_artifact(model_file)
    model = bundle["model"]
    audit_file = artifacts / f"{name}_split.json"
    audit = json.loads(audit_file.read_text(encoding="utf-8"))
    rows, image_dir, labels_file = dataset_rows(name)
    if audit["input_signature"] != _signature(rows, image_dir):
        raise ValueError("Input data changed after the split was frozen; retrain before evaluating")
    x, y = features_for_rows(rows, image_dir, name)
    with (artifacts / f"{name}_evaluation.csv").open(encoding="utf-8") as handle:
        membership = list(csv.DictReader(handle))
    if [row["file"] for row in rows] != [row["file"] for row in membership]:
        raise ValueError("Evaluation manifest does not match the feature rows")
    if name == "skin":
        positive = np.isin(y, bundle["referral_classes"])
        weights = np.array([float(label in bundle["referral_classes"]) for label in model.classes_])
    else:
        positive_ids = {"pad": [0, 1, 2], "dr": [0, 1]}.get(name, [0])
        positive = np.isin(y, positive_ids)
        weights = np.array([bundle["concern_weight"][int(label)] for label in model.classes_])
    threshold = float(bundle["referral_threshold"])
    results, predictions = {}, []
    for partition in ["validation", "test"]:
        indices = np.array([index for index, row in enumerate(membership)
                            if row["partition"] == partition], dtype=int)
        probabilities = model.predict_proba(x[indices])
        if name == "skin":
            scores = probabilities[:, np.flatnonzero(weights)].sum(axis=1)
        else:
            # Use the same summation order as training/serving at the exact
            # selected threshold; BLAS dot products can differ by one ULP.
            scores = sum(float(weight) * probabilities[:, column]
                         for column, weight in enumerate(weights))
        truth, flagged = positive[indices], scores >= threshold
        verdicts = binary_metrics(truth, flagged)
        verdicts.update({"images": len(indices), "positive_images": int(truth.sum()),
            "macro_f1": float(f1_score(y[indices], model.predict(x[indices]), average="macro")),
            "accuracy": float(accuracy_score(y[indices], model.predict(x[indices]))),
            "referral_score_auc": float(roc_auc_score(truth, scores)) if len(set(truth)) == 2 else None})
        if partition == "test":
            components = np.array([membership[index]["component"] for index in indices])
            verdicts["confidence_intervals"] = grouped_intervals(truth, flagged, components)
            for offset, index in enumerate(indices):
                predictions.append({"file": rows[index]["file"], "component": components[offset],
                    "label": str(y[index]), "positive": bool(truth[offset]),
                    "score": float(scores[offset]), "referred": bool(flagged[offset])})
        results[partition] = verdicts
    engineering_gate = (audit["components_disjoint"] and
                        results["validation"]["recall"] is not None and
                        results["validation"]["recall"] >= 0.90 - 1e-12 and
                        results["validation"]["specificity"] is not None and
                        results["validation"]["specificity"] > 0 and
                        results["test"]["positive_images"] >= 10 and
                        results["test"]["recall"] >= 0.80)
    report = {"dataset": name, "model_sha256": hashlib.sha256(model_file.read_bytes()).hexdigest(),
        "labels_sha256": hashlib.sha256(labels_file.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "labels_hash_format": "UTF-8 CSV bytes with CRLF normalized to LF",
        "sklearn_version": sklearn.__version__, "threshold": threshold,
        "threshold_selection": "validation_positive_scores_only_target_recall_0.90",
        "threshold_numerical_margin": 1e-12,
        "test_used_for_classifier_or_threshold_selection": False,
        "test_used_for_research_release_gate": True, "clinically_validated": False,
        "engineering_gate_passed": bool(engineering_gate),
        "research_release_floor": {"validation_recall": 0.90, "heldout_recall": 0.80,
                                   "minimum_positive_holdout_images": 10},
        "gate_limitation": "Research integrity/validation gate; not a clinical safety acceptance test.",
        "split_audit": audit, "metrics": results}
    (artifacts / f"{name}_holdout.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (artifacts / f"{name}_holdout_predictions.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(predictions[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(predictions)
    print(json.dumps({"dataset": name, "engineering_gate": engineering_gate,
                      "validation": results["validation"], "test": results["test"]}, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("datasets", nargs="+", choices=["skin", "tb", "pad", "mpox", "msld", "dr", "oral"])
    parser.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args()
    for dataset in args.datasets:
        evaluate(dataset, args.artifacts)
