"""Research releases preserve evaluated bytes and never audit training samples."""
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import joblib
import numpy as np
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))
import audit_skin_tones
import promote_imaging
from app.ai.skin_features import FEATURE_NAMES


class ImagingReleaseTests(unittest.TestCase):
    def test_rejected_candidate_leaves_existing_model_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root / "candidate", root / "serving"
            source.mkdir()
            target.mkdir()
            model = DecisionTreeClassifier(max_depth=1, random_state=42).fit(
                np.array([[0] * len(FEATURE_NAMES), [1] * len(FEATURE_NAMES)]), [0, 1])
            joblib.dump({"model": model, "features": FEATURE_NAMES, "referral_threshold": 0.5},
                        source / "pad_model.joblib")
            digest = hashlib.sha256((source / "pad_model.joblib").read_bytes()).hexdigest()
            (source / "pad_holdout.json").write_text(json.dumps({"model_sha256": digest,
                "threshold": 0.5, "engineering_gate_passed": False}), encoding="utf-8")
            (target / "pad_model.joblib").write_bytes(b"existing serving model")
            result = promote_imaging.promote(source, target, ["pad"])
            self.assertFalse(result["models"]["pad"]["promoted"])
            self.assertEqual(b"existing serving model", (target / "pad_model.joblib").read_bytes())
            # A modified model must fail before deserialization/copying.
            (source / "pad_model.joblib").write_bytes(b"changed after evaluation")
            with self.assertRaisesRegex(ValueError, "changed after evaluation"):
                promote_imaging.promote(source, target, ["pad"])
            self.assertEqual(b"existing serving model", (target / "pad_model.joblib").read_bytes())

    def test_missing_audit_record_cannot_partially_replace_serving_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root / "candidate", root / "serving"
            source.mkdir()
            target.mkdir()
            model = DecisionTreeClassifier(random_state=42).fit(
                np.array([[0] * len(FEATURE_NAMES), [1] * len(FEATURE_NAMES)]), [0, 1])
            joblib.dump({"model": model, "features": FEATURE_NAMES, "referral_threshold": 0.5},
                        source / "pad_model.joblib")
            digest = hashlib.sha256((source / "pad_model.joblib").read_bytes()).hexdigest()
            (source / "pad_holdout.json").write_text(json.dumps({"model_sha256": digest,
                "threshold": 0.5, "engineering_gate_passed": True}), encoding="utf-8")
            (source / "pad_metrics.json").write_text("candidate metrics", encoding="utf-8")
            (target / "pad_metrics.json").write_text("previous metrics", encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                promote_imaging.promote(source, target, ["pad"])
            self.assertEqual("previous metrics", (target / "pad_metrics.json").read_text(encoding="utf-8"))

    def test_tone_audit_only_accepts_test_membership_and_keeps_missing_groups_visible(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            labels = root / "data/real/imaging/pad_labels.csv"
            labels.parent.mkdir(parents=True)
            labels.write_text("file,fitspatrick\ntrain.png,1\ntest.png,5\n", encoding="utf-8")
            (artifacts / "pad_model.joblib").write_bytes(b"frozen model")
            digest = hashlib.sha256(b"frozen model").hexdigest()
            (artifacts / "pad_holdout.json").write_text(json.dumps({"model_sha256": digest}), encoding="utf-8")
            (artifacts / "pad_evaluation.csv").write_text(
                "file,partition\ntrain.png,train\ntest.png,test\n", encoding="utf-8")
            predictions = artifacts / "pad_holdout_predictions.csv"
            with predictions.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["file", "component", "positive", "referred"])
                writer.writeheader()
                writer.writerow({"file": "test.png", "component": "2", "positive": False, "referred": False})
            with patch.object(audit_skin_tones, "ROOT", root):
                result = audit_skin_tones.audit(artifacts, root / "report.md")
                self.assertEqual(1, result["test_images"])
                self.assertEqual(0, result["tones"]["1"]["n"])
                self.assertEqual(1, result["tones"]["5"]["n"])
                self.assertIsNone(result["tones"]["5"]["recall"])
                self.assertIsNone(result["tones"]["6"]["recall"])
                predictions.write_text(predictions.read_text(encoding="utf-8").replace("test.png", "train.png"),
                                       encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "exactly the frozen test"):
                    audit_skin_tones.audit(artifacts, root / "report.md")


if __name__ == "__main__":
    unittest.main()
