"""Evaluation independence and low-score referral calibration regressions."""
import csv
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("imaging_training", ROOT / "ml/imaging_training.py")
training = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(training)


class ImagingTrainingTests(unittest.TestCase):
    def test_threshold_handles_positive_scores_below_the_old_grid(self):
        scores = np.array([0.001, 0.002, 0.003, 0.9])
        positive = np.array([True, True, True, False])
        threshold = training.recall_threshold(scores, positive, 0.9)
        self.assertAlmostEqual(0.001, threshold, places=10)
        self.assertEqual(1.0, (scores[positive] >= threshold).mean())
        self.assertEqual(1.0, ((scores[positive] - 5e-15) >= threshold).mean(),
                         "parallel tree accumulation must not drop a validation boundary case")
        with self.assertRaises(ValueError):
            training.recall_threshold(scores, np.zeros(4, dtype=bool))
        with self.assertRaises(ValueError):
            training.recall_threshold([float("nan")], [True])

    def test_lossless_compact_storage_preserves_runtime_features(self):
        from app.ai.skin_features import extract_features
        image = Image.fromarray(np.random.default_rng(7).integers(0, 256, (211, 317, 3), dtype=np.uint8))
        original = extract_features(image)
        reduced, _, _ = training._fingerprint(image)
        buffer = io.BytesIO()
        reduced.save(buffer, format="PNG")
        with Image.open(io.BytesIO(buffer.getvalue())) as compact:
            np.testing.assert_array_equal(original, extract_features(compact))

    def test_duplicates_conflicts_and_subjects_do_not_cross_partitions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rows = []
            rng = np.random.default_rng(15)
            for index in range(40):
                name = f"{index}.png"
                image = Image.fromarray(rng.integers(0, 256, (64, 80, 3), dtype=np.uint8))
                image.save(root / name)
                rows.append({"file": name, "label_id": str(index % 2), "patient_id": f"p{index // 2}"})
            (root / "duplicate.png").write_bytes((root / "0.png").read_bytes())
            rows.append({"file": "duplicate.png", "label_id": "0", "patient_id": "duplicate-patient"})
            (root / "conflict.png").write_bytes((root / "1.png").read_bytes())
            rows.append({"file": "conflict.png", "label_id": "0", "patient_id": "conflicting-patient"})
            with Image.open(root / "0.png") as original:
                altered = np.array(original)
            altered[20, 20, 0] ^= 31
            Image.fromarray(altered).save(root / "near.png")
            rows.append({"file": "near.png", "label_id": "0", "patient_id": "unknown-shared-subject"})
            with patch.object(training, "CACHE", root / "cache"):
                parts = training.make_split(rows, root, "fixture", root / "artifacts",
                                             group_field="patient_id", fraction=0.2)
            self.assertEqual(40, sum(len(part) for part in parts))
            with (root / "artifacts/fixture_evaluation.csv").open(encoding="utf-8") as handle:
                manifest = list(csv.DictReader(handle))
            roles = {}
            for row in manifest:
                if row["partition"] == "excluded":
                    continue
                roles.setdefault(row["subject_id"], set()).add(row["partition"])
            self.assertTrue(all(len(partitions) == 1 for partitions in roles.values()))
            by_file = {row["file"]: row for row in manifest}
            self.assertNotEqual(by_file["0.png"]["pixel_sha256"], by_file["near.png"]["pixel_sha256"])
            self.assertEqual(by_file["0.png"]["component"], by_file["near.png"]["component"])
            self.assertEqual(by_file["0.png"]["partition"], by_file["near.png"]["partition"])
            audit = json.loads((root / "artifacts/fixture_split.json").read_text(encoding="utf-8"))
            self.assertTrue(audit["components_disjoint"])
            self.assertEqual(2, audit["exclusions"]["conflicting_labels_for_same_pixels"])
            self.assertEqual(1, audit["exclusions"]["exact_pixel_duplicate"])


if __name__ == "__main__":
    unittest.main()
