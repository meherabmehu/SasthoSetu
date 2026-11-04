"""Recalibrate a frozen classifier using validation cases only, never test cases.

Also applies the shared numerical margin for parallel tree probability sums.
Run evaluate_imaging.py again afterwards; old model hashes no longer match.
"""
import argparse
import csv
import json
from pathlib import Path

import joblib
import numpy as np

from evaluate_imaging import dataset_rows
from imaging_training import _signature, features_for_rows, recall_threshold
from app.ai.artifact_loading import load_artifact

DATASETS = ["skin", "tb", "pad", "mpox", "msld", "dr", "oral"]


def calibrate(name, artifacts):
    artifacts = Path(artifacts)
    rows, image_dir, _ = dataset_rows(name)
    audit = json.loads((artifacts / f"{name}_split.json").read_text(encoding="utf-8"))
    if _signature(rows, image_dir) != audit["input_signature"]:
        raise ValueError("Input data changed since the split was frozen")
    with (artifacts / f"{name}_evaluation.csv").open(encoding="utf-8") as handle:
        membership = list(csv.DictReader(handle))
    if [row["file"] for row in rows] != [row["file"] for row in membership]:
        raise ValueError("Frozen split does not match source rows")
    indices = np.array([index for index, row in enumerate(membership)
                        if row["partition"] == "validation"], dtype=int)
    x, y = features_for_rows(rows, image_dir, name)
    path = artifacts / f"{name}_model.joblib"
    bundle = load_artifact(path)
    probabilities = bundle["model"].predict_proba(x[indices])
    if name == "skin":
        columns = [i for i, label in enumerate(bundle["model"].classes_)
                   if label in bundle["referral_classes"]]
        scores = probabilities[:, columns].sum(axis=1)
        positives = np.isin(y[indices], bundle["referral_classes"])
    else:
        scores = sum(bundle["concern_weight"][int(label)] * probabilities[:, column]
                     for column, label in enumerate(bundle["model"].classes_))
        positives = np.isin(y[indices], {"pad": [0, 1, 2], "dr": [0, 1]}.get(name, [0]))
    bundle["referral_threshold"] = recall_threshold(scores, positives)
    bundle["calibration"] = {"partition": "validation", "target_recall": 0.90,
                             "numerical_margin": 1e-12, "test_used": False}
    joblib.dump(bundle, path, compress=3)
    metric_path = artifacts / f"{name}_metrics.json"
    metrics = json.loads(metric_path.read_text(encoding="utf-8"))
    metrics["referral_threshold"] = bundle["referral_threshold"]
    metrics["calibration"] = bundle["calibration"]
    if name == "skin":
        metrics["split_strategy"] = "lesion_groups_and_pixel_perceptual_components"
    metric_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"{name}: validation-only threshold {bundle['referral_threshold']:.15f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--datasets", nargs="+", choices=DATASETS, default=DATASETS)
    args = parser.parse_args()
    for dataset in args.datasets:
        calibrate(dataset, args.artifacts)
