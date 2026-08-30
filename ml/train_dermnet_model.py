# -*- coding: utf-8 -*-
"""Train the general skin condition classifier on DermNet.

HAM10000 answers one question well: is this pigmented lesion cancer. It cannot
answer the question people here actually ask, which is far more often "what is
this rash". Ringworm, scabies, eczema and nail fungus are not in HAM10000 at
all, so a model trained only on it will confidently call ringworm an ordinary
mole.

DermNet covers 23 conditions across 15,557 clinical photographs, and unlike
HAM10000 these are ordinary photographs rather than dermatoscope images — much
closer to what a phone camera produces.

The model predicts a **referral band**, not a diagnosis. Picking one of 23
conditions from a photograph is not something to put in front of a patient; the
useful and defensible output is whether to see a doctor and how soon. The
mapping from condition to band lives in ml/fetch_medical_datasets.py and is the
part a clinician should review first.

    python ml/train_dermnet_model.py
    python ml/train_dermnet_model.py --limit 3000     (quick check)

Output: backend/app/ai/artifacts/dermnet_model.joblib, dermnet_metrics.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
from PIL import Image
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import classification_report, f1_score, recall_score

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runtime import configure_worker_cpus  # noqa: E402

configure_worker_cpus()

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.skin_features import FEATURE_NAMES, extract_features  # noqa: E402

IMAGING = ROOT / "data" / "real" / "imaging"
IMAGES = IMAGING / "dermnet"
LABELS = IMAGING / "dermnet_labels.csv"
ART = ROOT / "backend" / "app" / "ai" / "artifacts"

SEED = 42

# Ordered least to most urgent.
BANDS = ["watch_it", "get_it_checked", "see_doctor_soon"]


def _load(limit: int | None):
    with LABELS.open(encoding="utf-8") as fh:
        records = list(csv.DictReader(fh))

    if limit:
        rng = np.random.default_rng(SEED)
        by_band: dict[str, list[dict]] = {}
        for record in records:
            by_band.setdefault(record["urgency"], []).append(record)
        share = limit / len(records)
        records = []
        for group in by_band.values():
            take = max(50, int(len(group) * share))
            index = rng.permutation(len(group))[:take]
            records.extend(group[i] for i in index)

    features, bands, conditions, splits = [], [], [], []
    started = time.time()

    for position, record in enumerate(records, start=1):
        path = IMAGES / record["file"]
        if not path.exists():
            continue
        try:
            with Image.open(path) as image:
                vector = extract_features(image)
        except Exception:  # noqa: BLE001 - one bad file must not stop training
            continue

        features.append(vector)
        bands.append(record["urgency"])
        conditions.append(record["condition"])
        splits.append(record["split"])

        if position % 2000 == 0:
            rate = position / (time.time() - started)
            print(f"  {position:,}/{len(records):,} images ({rate:.0f}/s)",
                  flush=True)

    return (np.array(features, dtype=np.float32), np.array(bands),
            np.array(conditions), np.array(splits))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if not LABELS.exists():
        print(f"{LABELS.relative_to(ROOT)} is missing — run "
              "python ml/fetch_medical_datasets.py --only dermnet first")
        raise SystemExit(1)

    print("Extracting image features")
    x, bands, conditions, splits = _load(args.limit)
    print(f"  {len(x):,} images, {x.shape[1]} features each")

    # DermNet ships its own train/test division, so it is honoured rather than
    # reshuffled: the published split is what other results are quoted against.
    rng = np.random.default_rng(SEED)
    train_index = np.flatnonzero(splits == "train")
    rng.shuffle(train_index)
    cut = int(len(train_index) * 0.9)
    fit_index, val_index = train_index[:cut], train_index[cut:]
    test_index = np.flatnonzero(splits != "train")

    print(f"  train={len(fit_index):,} val={len(val_index):,} "
          f"test={len(test_index):,}")

    model = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.1, max_depth=8,
        class_weight="balanced", random_state=SEED,
    )
    model.fit(x[fit_index], bands[fit_index])

    val_predicted = model.predict(x[val_index])
    val_f1 = f1_score(bands[val_index], val_predicted, average="macro")
    print(f"  val macro-F1 = {val_f1:.4f}")

    truth = bands[test_index]

    # Taking the most likely band sends 167 genuinely urgent cases home,
    # because the three bands are close in probability and "watch it" is the
    # larger class. The costs are not symmetric: telling someone with
    # cellulitis to wait is a different kind of error from being cautious
    # about a wart.
    #
    # So the decision is made on cumulative probability instead. A case is
    # escalated when enough probability mass sits at or above a band, with
    # thresholds chosen on the validation split — never on the test split.
    classes = list(model.classes_)
    urgent_col = classes.index("see_doctor_soon")
    checked_col = classes.index("get_it_checked")

    val_prob = model.predict_proba(x[val_index])
    val_truth = bands[val_index]

    def _escalate(probabilities, urgent_at, checked_at):
        urgent_score = probabilities[:, urgent_col]
        checked_score = urgent_score + probabilities[:, checked_col]
        out = np.full(len(probabilities), "watch_it", dtype=object)
        out[checked_score >= checked_at] = "get_it_checked"
        out[urgent_score >= urgent_at] = "see_doctor_soon"
        return out

    # Two thresholds are needed, and they trade against each other. Pushing
    # urgent recall to 90% escalates almost everything, which makes the answer
    # worthless — a triage tool that always says "see a doctor" is not triage.
    #
    # 75% is the point where the great majority of urgent cases are caught
    # while "watch it" still means something. The remaining safety net is the
    # middle band: what matters most is that an urgent case is not dismissed
    # outright, and that is measured separately below.
    target_recall = 0.75
    urgent_at = 0.05
    actual = val_truth == "see_doctor_soon"
    for candidate in sorted(np.linspace(0.05, 0.7, 66), reverse=True):
        if actual.sum() == 0:
            break
        flagged = val_prob[:, urgent_col] >= candidate
        if float((flagged & actual).sum() / actual.sum()) >= target_recall:
            urgent_at = float(candidate)
            break

    # The middle band is the safety net: an urgent case that slips past the
    # first threshold should still land on "get it checked" rather than
    # "watch it". Chosen so that at most 5% of urgent cases are dismissed.
    checked_at = 0.95
    for candidate in sorted(np.linspace(0.2, 0.95, 76), reverse=True):
        if actual.sum() == 0:
            break
        score = val_prob[:, urgent_col] + val_prob[:, checked_col]
        dismissed_share = float(
            ((score < candidate) & actual).sum() / actual.sum()
        )
        if dismissed_share <= 0.05:
            checked_at = float(candidate)
            break

    print(f"  urgent threshold  = {urgent_at:.2f} "
          f"(validation, target recall {target_recall:.0%})")
    print(f"  checked threshold = {checked_at:.2f} "
          f"(validation, <=5% of urgent cases dismissed)")

    test_prob = model.predict_proba(x[test_index])
    predicted = _escalate(test_prob, urgent_at, checked_at)

    macro_f1 = f1_score(truth, predicted, average="macro")
    accuracy = float((predicted == truth).mean())

    urgent_truth = truth == "see_doctor_soon"
    urgent_pred = predicted == "see_doctor_soon"
    urgent_recall = float(recall_score(urgent_truth, urgent_pred,
                                       zero_division=0))
    dismissed = int((urgent_truth & (predicted == "watch_it")).sum())

    print(f"\ntest macro-F1 = {macro_f1:.4f}  accuracy = {accuracy:.4f}")
    print(f"urgent recall = {urgent_recall:.4f}")
    print(f"urgent cases told to stay home = {dismissed} "
          f"of {int(urgent_truth.sum())}")
    print()
    print(classification_report(truth, predicted, zero_division=0))

    ART.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": model, "features": FEATURE_NAMES, "bands": BANDS,
         "urgent_threshold": urgent_at, "checked_threshold": checked_at},
        ART / "dermnet_model.joblib", compress=3,
    )
    (ART / "dermnet_metrics.json").write_text(
        json.dumps({
            "validation_macro_f1": round(float(val_f1), 4),
            "test_macro_f1": round(float(macro_f1), 4),
            "test_accuracy": round(accuracy, 4),
            "urgent_recall": round(urgent_recall, 4),
            "urgent_threshold": round(urgent_at, 3),
            "checked_threshold": round(checked_at, 3),
            "urgent_dismissed_as_watch": dismissed,
            "urgent_total": int(urgent_truth.sum()),
            "test_size": int(len(test_index)),
            "n_images": int(len(x)),
            "n_conditions": int(len(set(conditions.tolist()))),
            "seed": SEED,
        }, indent=2),
        encoding="utf-8",
    )
    print(f"\nartifacts -> {ART}")


if __name__ == "__main__":
    main()
