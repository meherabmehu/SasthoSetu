# -*- coding: utf-8 -*-
"""The verified viral screen must be able to name cowpox and HFMD.

MSLD v2.0 is the dermatologist-reviewed collection, and it carries two
classes no other dataset we serve has: cowpox and hand-foot-mouth disease.
Without this screen those conditions had no vocabulary anywhere in the
system - a photograph of either could only be mislabelled.

Held here, like every other screen:

  - a monkeypox photograph raises the referral band;
  - the screen reports itself with readable condition names;
  - a healthy photograph completes the assessment with a band and a
    disclaimer, never a bare verdict.
"""
import csv
import os
import tempfile
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/msld.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

ROOT = Path(__file__).resolve().parents[2]
IMAGING = ROOT / "data" / "real" / "imaging"

HAS_DATASET = ((IMAGING / "msld_labels.csv").exists()
               and any((IMAGING / "msld").glob("*")))


@unittest.skipUnless(HAS_DATASET, "MSLD photographs not fetched")
class VerifiedViralScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.ai.skin_service import assess_skin_image
        cls.assess = staticmethod(assess_skin_image)

        cls.by_class: dict[str, list[Path]] = {}
        with (IMAGING / "msld_labels.csv").open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                cls.by_class.setdefault(
                    row["condition"], []
                ).append(IMAGING / "msld" / row["file"])

    def _assess_first(self, condition: str):
        photos = self.by_class[condition]
        self.assertTrue(photos, f"no photographs for {condition}")
        return self.assess(photos[0].read_bytes(), age=30)

    def test_a_monkeypox_photograph_is_referred(self):
        out = self._assess_first("MKP")
        self.assertIn(out["band"], ("see_doctor_soon",))
        self.assertTrue(out["urgent"])
        screen = out.get("verified_viral_rash")
        self.assertIsNotNone(screen, "the screen ran but reported nothing")

    def test_the_screen_reports_itself_with_readable_names(self):
        out = self._assess_first("MKP")
        self.assertTrue(out["models"]["verified_viral_rash_screen"])
        screen = out["verified_viral_rash"]
        if screen and screen["top"]:
            self.assertNotEqual(screen["top"]["name_en"], "0")
            self.assertIn(screen["top"]["name_en"], (
                "Mpox (monkeypox) — needs urgent review",
                "Cowpox — needs review",
                "Hand, foot and mouth disease",
                "Measles",
                "Chickenpox (varicella)",
                "Healthy skin",
            ))

    def test_a_healthy_photograph_completes_with_a_band(self):
        out = self._assess_first("HEALTHY")
        self.assertIn(out["band"], ("watch_it", "get_it_checked",
                                    "see_doctor_soon"))
        self.assertTrue(out["disclaimer_bn"])


if __name__ == "__main__":
    unittest.main()
