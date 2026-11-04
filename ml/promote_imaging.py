"""Install evaluated research artifacts after checking integrity and compatibility.

This local artifact operation never deploys a service or approves clinical use.
Candidates failing the recorded research gate remain outside the serving path.
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.artifact_loading import load_artifact
from app.ai.skin_features import FEATURE_NAMES

DATASETS = ["skin", "tb", "pad", "mpox", "msld", "dr", "oral"]


def promote(source, target, datasets):
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target:
        raise ValueError("Evaluate candidates outside the serving directory first")
    release = {"scope": "demo/research only", "clinically_validated": False, "models": {}}
    suffixes = ["metrics.json", "split.json", "evaluation.csv", "holdout.json",
                "holdout_predictions.csv", "model.joblib"]
    accepted_names = []
    for name in datasets:
        report = json.loads((source / f"{name}_holdout.json").read_text(encoding="utf-8"))
        model_path = source / f"{name}_model.joblib"
        actual_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
        if actual_hash != report["model_sha256"]:
            raise ValueError(f"{name}: candidate changed after evaluation")
        bundle = load_artifact(model_path)
        if (list(bundle.get("features", FEATURE_NAMES)) != list(FEATURE_NAMES)
                or bundle["model"].n_features_in_ != len(FEATURE_NAMES)):
            raise ValueError(f"{name}: training features differ from serving features")
        if float(bundle["referral_threshold"]) != report["threshold"]:
            raise ValueError(f"{name}: threshold differs from the evaluated value")
        accepted = report["engineering_gate_passed"]
        release["models"][name] = {"promoted": accepted, "candidate_sha256": actual_hash,
            "reason": "passed research integrity and recall floor" if accepted else "failed research release gate"}
        if not accepted:
            print(f"RETAIN existing {name}: candidate failed gate")
            continue
        for suffix in suffixes:
            if not (source / f"{name}_{suffix}").is_file():
                raise FileNotFoundError(f"{name}: missing evaluation record {suffix}")
        accepted_names.append(name)
    # Finish all integrity/compatibility checks before changing any serving files.
    target.mkdir(parents=True, exist_ok=True)
    for name in accepted_names:
        # Copy the small audit records too; model file is replaced last.
        for suffix in suffixes:
            original = source / f"{name}_{suffix}"
            destination = target / original.name
            temporary = target / (original.name + ".installing")
            shutil.copyfile(original, temporary)
            temporary.replace(destination)
        print(f"Installed evaluated demo model: {name}")
    (target / "imaging_release.json").write_text(json.dumps(release, indent=2), encoding="utf-8")
    return release


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, default=ROOT / "backend/app/ai/artifacts")
    parser.add_argument("--datasets", nargs="+", choices=DATASETS, default=DATASETS)
    args = parser.parse_args()
    promote(args.source, args.target, args.datasets)
