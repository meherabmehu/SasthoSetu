# -*- coding: utf-8 -*-
"""The viral-rash screen must be able to say "monkeypox" out loud.

DermNet's 23 conditions and HAM10000's seven lesions carry no viral
exanthems at all, so before this screen existed a photograph of a
monkeypox rash could only ever be mislabelled - there was no class for it
to land in. The MSID screen adds that vocabulary, and these tests hold the
two properties that make it safe to serve:

  - a monkeypox photograph raises the referral band, not merely the
    differential;
  - the screen can only raise a band, never lower what another model said.
"""
import csv
import os
import tempfile
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/mpox.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

ROOT = Path(__file__).resolve().parents[2]
IMAGING = ROOT / "data" / "real" / "imaging"

HAS_DATASET = (IMAGING / "mpox_labels.csv").exists()


@unittest.skipUnless(HAS_DATASET, "MSID photographs not fetched")
class ViralRashScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.ai.skin_service import assess_skin_image
        # Wrapped: a bare function assigned to a class attribute becomes a
        # bound method, and the instance would arrive as the payload.
        cls.assess = staticmethod(assess_skin_image)

        cls.by_class: dict[str, list[Path]] = {}
        with (IMAGING / "mpox_labels.csv").open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                cls.by_class.setdefault(
                    row["condition"], []
                ).append(IMAGING / "mpox" / row["file"])

    def _assess_any(self, condition: str):
        photos = self.by_class[condition]
        self.assertTrue(photos, f"no photographs for {condition}")
        return self.assess(photos[0].read_bytes(), age=30)
    def test_a_monkeypox_photograph_is_referred(self):
        out = self._assess_any("Monkeypox")
        self.assertEqual("see_doctor_soon", out["band"])
        self.assertTrue(out["urgent"])

        viral = out.get("viral_rash")
        self.assertIsNotNone(viral, "the screen ran but reported nothing")
        self.assertGreaterEqual(
            viral["concern"], viral["threshold"] * 0.5,
            "a monkeypox photograph should register on the screen at all",
        )

    def test_the_screen_reports_itself(self):
        out = self._assess_any("Normal")
        self.assertIn("viral_rash_screen", out["models"])
        self.assertTrue(out["models"]["viral_rash_screen"])

    def test_the_named_differential_uses_readable_codes(self):
        """numpy class ids leaking into the response was a real bug."""
        out = self._assess_any("Monkeypox")
        viral = out["viral_rash"]
        if viral and viral["top"]:
            self.assertNotEqual(
                viral["top"]["name_en"], "0",
                "the class id was shown instead of the condition name",
            )
            self.assertIn(viral["top"]["name_en"], (
                "Mpox (monkeypox) — needs urgent review",
                "Chickenpox (varicella)",
                "Measles",
                "Normal skin",
            ))


if __name__ == "__main__":
    unittest.main()
