import importlib.util
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from sklearn.exceptions import InconsistentVersionWarning

from app.ai.artifact_loading import IncompatibleArtifact, load_artifact


class ArtifactIntegrityTests(unittest.TestCase):
    def test_version_mismatch_is_rejected_instead_of_silenced(self):
        def incompatible(*args):
            warnings.warn(InconsistentVersionWarning(estimator_name="test",
                current_sklearn_version="1.5.2", original_sklearn_version="1.6.1"), stacklevel=2)
        with patch("app.ai.artifact_loading.joblib.load", side_effect=incompatible):
            with self.assertRaises(IncompatibleArtifact):
                load_artifact(Path("test_model.joblib"))

    def test_optional_tb_screen_is_unavailable_when_incompatible(self):
        from app.ai import xray_service
        xray_service._tb_bundle.cache_clear()
        try:
            with patch("app.ai.xray_service.load_artifact", side_effect=IncompatibleArtifact("rebuild")):
                self.assertIsNone(xray_service._tb_bundle())
        finally:
            xray_service._tb_bundle.cache_clear()


class GroupedSplitTests(unittest.TestCase):
    def test_repeated_subjects_and_duplicate_images_stay_together(self):
        path = Path(__file__).resolve().parents[2] / "ml" / "grouped_split.py"
        spec = importlib.util.spec_from_file_location("grouped_split", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            paths, groups = [], []
            for index in range(40):
                path = Path(folder) / str(index)
                # Duplicate content across two differently identified subjects.
                path.write_bytes(str(0 if index == 39 else index).encode())
                paths.append(path)
                groups.append(f"subject-{index // 2}")
            splits = module.grouped_image_split(paths, groups)
            membership = {int(index): split for split, indices in enumerate(splits) for index in indices}
            for index in range(0, 40, 2):
                self.assertEqual(membership[index], membership[index + 1])
            self.assertEqual(membership[0], membership[39])
            self.assertEqual(set(range(40)), set(membership))
            with self.assertRaises(ValueError):
                module.grouped_image_split(paths, [""] * 40)
            for missing in [None, float("nan"), "None"]:
                with self.subTest(missing=missing), self.assertRaises(ValueError):
                    module.grouped_image_split(paths, [missing] * 40)
