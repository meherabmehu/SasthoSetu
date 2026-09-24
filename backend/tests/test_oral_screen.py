# -*- coding: utf-8 -*-
"""The oral screen must be able to say "cancer".

Oral cancer is among the commonest cancers in Bangladesh - betel-quid and
tobacco chewing see to that - and it presents late precisely because
nobody photographs the inside of a mouth early. Before this screen the
system had no vocabulary for it.

Held here, mirroring the eye screen:

  - a carcinoma photograph escalates the band;
  - findings are reported by readable name;
  - a normal photograph still routes to a doctor - no screen may clear.
"""
import csv
import os
import tempfile
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/oral.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

ROOT = Path(__file__).resolve().parents[2]
IMAGING = ROOT / "data" / "real" / "imaging"

HAS_DATASET = ((IMAGING / "oral_labels.csv").exists()
               and any((IMAGING / "oral").glob("*")))


class OralModelAvailabilityTests(unittest.TestCase):
    def test_the_model_reports_available(self):
        from app.ai.oral_service import model_available
        self.assertTrue(model_available())


@unittest.skipUnless(HAS_DATASET, "mouth photographs not fetched")
class OralScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.ai.oral_service import assess_oral_photo
        cls.assess = staticmethod(assess_oral_photo)

        cls.by_class: dict[str, list[Path]] = {}
        with (IMAGING / "oral_labels.csv").open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                cls.by_class.setdefault(
                    row["condition"], []
                ).append(IMAGING / "oral" / row["file"])

    def _assess_first(self, condition: str):
        photos = self.by_class[condition]
        self.assertTrue(photos, f"no photographs for {condition}")
        return self.assess(photos[0].read_bytes(), age=50)

    def test_a_carcinoma_photograph_escalates(self):
        out = self._assess_first("oral_scc")
        self.assertEqual("urgent_review", out["band"])
        self.assertTrue(out["urgent"])

    def test_findings_use_readable_names(self):
        out = self._assess_first("oral_scc")
        for finding in out["findings"]:
            self.assertIn(finding["finding"], ("oral_scc", "oral_normal"))

    def test_a_normal_photograph_still_routes_to_a_doctor(self):
        out = self._assess_first("oral_normal")
        self.assertEqual("doctor_review", out["band"])
        self.assertIn("বাতিল করা যায় না", out["disclaimer_bn"])


if __name__ == "__main__":
    unittest.main()
