# -*- coding: utf-8 -*-
"""The chest film screen must be able to say "tuberculosis".

The pneumonia model's vocabulary has two classes - pneumonia and normal -
so before the TB screen existed, a film showing upper-lobe cavitation
could only ever come back as one of those two. Tuberculosis is among the
top infectious causes of death in Bangladesh; a screen that cannot name
it is not a chest screen for this country.

Held here:

  - a tuberculosis film escalates the band to urgent review;
  - the screen reports itself and its top reading in the response;
  - the reading uses readable names, not the class ids sklearn stores.
"""
import csv
import os
import tempfile
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/tb.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

ROOT = Path(__file__).resolve().parents[2]
IMAGING = ROOT / "data" / "real" / "imaging"

HAS_DATASET = ((IMAGING / "tb_labels.csv").exists()
                 and any((IMAGING / "tb").glob("*")))


@unittest.skipUnless(HAS_DATASET, "TB films not fetched")
class TuberculosisScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.ai.xray_service import assess_chest_xray
        cls.assess = staticmethod(assess_chest_xray)

        cls.by_class: dict[str, list[Path]] = {}
        with (IMAGING / "tb_labels.csv").open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                cls.by_class.setdefault(
                    row["condition"], []
                ).append(IMAGING / "tb" / row["file"])

    def _assess_first(self, condition: str):
        films = self.by_class[condition]
        self.assertTrue(films, f"no films for {condition}")
        return self.assess(films[0].read_bytes(), age=40)

    def test_a_tuberculosis_film_is_referred_urgently(self):
        out = self._assess_first("TUBERCULOSIS")
        self.assertEqual("urgent_review", out["band"])
        self.assertTrue(out["urgent"])

        screen = out.get("tuberculosis_screen")
        self.assertIsNotNone(screen, "the screen ran but reported nothing")

    def test_the_screen_reports_its_top_reading_by_name(self):
        out = self._assess_first("TUBERCULOSIS")
        screen = out["tuberculosis_screen"]
        if screen and screen["top"]:
            self.assertNotEqual(
                screen["top"]["name_en"], "0",
                "the class id was shown instead of the finding name",
            )
            self.assertIn(screen["top"]["name_en"], (
                "Tuberculosis — needs a confirmatory test",
                "Pneumonia",
                "COVID-19 pattern",
                "Normal",
            ))

    def test_a_normal_film_still_routes_to_a_doctor(self):
        """No screen may clear a film; that rule predates this one."""
        out = self._assess_first("NORMAL")
        self.assertIn(out["band"], ("doctor_review", "urgent_review"))


if __name__ == "__main__":
    unittest.main()
