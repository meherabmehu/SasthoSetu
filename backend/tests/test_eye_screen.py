# -*- coding: utf-8 -*-
"""The eye screen must be able to say "retinopathy".

Diabetes is one of the commonest chronic diseases in Bangladesh and
retinopathy one of its blindest complications; before this screen the
system had no vocabulary for the eye at all.

Held here, mirroring the chest-film screen:

  - a sight-threatening photograph escalates the band;
  - the model reports itself as available;
  - a healthy photograph still routes to a doctor - no screen may clear.
"""
import csv
import os
import tempfile
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/eye.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

ROOT = Path(__file__).resolve().parents[2]
IMAGING = ROOT / "data" / "real" / "imaging"

HAS_DATASET = ((IMAGING / "dr_labels.csv").exists()
               and any((IMAGING / "dr").glob("*")))


class EyeModelAvailabilityTests(unittest.TestCase):
    def test_the_model_reports_available(self):
        from app.ai.eye_service import model_available
        self.assertTrue(model_available())


@unittest.skipUnless(HAS_DATASET, "retina photographs not fetched")
class EyeScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.ai.eye_service import assess_eye_photo
        cls.assess = staticmethod(assess_eye_photo)

        cls.by_class: dict[str, list[Path]] = {}
        with (IMAGING / "dr_labels.csv").open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                cls.by_class.setdefault(
                    row["condition"], []
                ).append(IMAGING / "dr" / row["file"])

    def _assess_first(self, condition: str):
        photos = self.by_class[condition]
        self.assertTrue(photos, f"no photographs for {condition}")
        return self.assess(photos[0].read_bytes(), age=55)

    def test_a_sight_threatening_photograph_escalates(self):
        """A single photograph can be a known miss - the measured recall is
        83%, and pretending one photograph must hit would be a test of
        luck. What must hold is that a sample of them mostly escalates."""
        photos = self.by_class["Proliferate DR"][:5]
        escalated = 0
        for photo in photos:
            out = self.assess(photo.read_bytes(), age=55)
            if out["band"] == "urgent_review":
                escalated += 1
        self.assertGreaterEqual(
            escalated, 3,
            f"only {escalated} of 5 sight-threatening photographs escalated",
        )
        first_out = self.assess(photos[0].read_bytes(), age=55)
        self.assertEqual("Ophthalmology",
                         first_out["recommended_specialty"])

    def test_findings_use_readable_names(self):
        out = self._assess_first("Severe DR")
        for finding in out["findings"]:
            self.assertNotEqual(finding["finding"], "0")

    def test_a_healthy_photograph_still_routes_to_a_doctor(self):
        """No screen may clear a photograph; a clear screen is not a clean
        bill of health and the wording must not pretend otherwise."""
        out = self._assess_first("Healthy")
        self.assertEqual("doctor_review", out["band"])
        self.assertIn("বাতিল করা যায় না", out["disclaimer_bn"])


if __name__ == "__main__":
    unittest.main()
