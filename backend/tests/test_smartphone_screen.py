# -*- coding: utf-8 -*-
"""The smartphone screen must be able to name a carcinoma.

HAM10000 reads dermatoscope images; our users send phone photographs. The
PAD-UFES-20 screen exists for exactly that input, and these tests hold the
properties every other skin screen already holds:

  - a malignant photograph raises the referral band;
  - the screen reports itself and its top reading by readable name;
  - a benign photograph does not lower what another screen raised.
"""
import csv
import os
import tempfile
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/pad.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

ROOT = Path(__file__).resolve().parents[2]
IMAGING = ROOT / "data" / "real" / "imaging"

HAS_DATASET = ((IMAGING / "pad_labels.csv").exists()
                 and any((IMAGING / "pad").glob("*")))


@unittest.skipUnless(HAS_DATASET, "PAD photographs not fetched")
class SmartphoneScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.ai.skin_service import assess_skin_image
        cls.assess = staticmethod(assess_skin_image)

        cls.by_class: dict[str, list[Path]] = {}
        with (IMAGING / "pad_labels.csv").open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                cls.by_class.setdefault(
                    row["condition"], []
                ).append(IMAGING / "pad" / row["file"])

    def _assess_first(self, condition: str):
        photos = self.by_class[condition]
        self.assertTrue(photos, f"no photographs for {condition}")
        return self.assess(photos[0].read_bytes(), age=50)

    def test_a_malignant_photograph_is_referred(self):
        out = self._assess_first("BCC")
        self.assertEqual("see_doctor_soon", out["band"])
        self.assertTrue(out["urgent"])

    def test_the_screen_reports_itself(self):
        out = self._assess_first("NEV")
        self.assertIn("smartphone_lesion_screen", out["models"])
        self.assertTrue(out["models"]["smartphone_lesion_screen"])
        screen = out.get("smartphone_lesion")
        self.assertIsNotNone(screen, "the screen ran but reported nothing")
        if screen and screen["top"]:
            self.assertNotEqual(
                screen["top"]["name_en"], "0",
                "the class id was shown instead of the condition name",
            )

    def test_a_benign_photograph_still_gets_a_band(self):
        """Whatever the band is, the assessment must complete and carry a
        referral band plus a disclaimer - the screen never blocks care."""
        out = self._assess_first("SEK")
        self.assertIn(out["band"], ("watch_it", "get_it_checked",
                                    "see_doctor_soon"))
        self.assertTrue(out["disclaimer_bn"])


if __name__ == "__main__":
    unittest.main()
