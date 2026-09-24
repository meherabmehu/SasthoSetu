# -*- coding: utf-8 -*-
"""The skin-tone audit must exist and say what it covers.

The audit is a document, not a service, so what a test can hold is its
shape: it must exist, report every Fitzpatrick group that the dataset
actually contains, and carry both halves - referral rates and malignant
recall - because either half alone tells a comfortable half of the story.
"""
import csv
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "docs" / "model_cards" / "skin_tone_audit.md"
LABELS = ROOT / "data" / "real" / "imaging" / "pad_labels.csv"


@unittest.skipUnless(LABELS.exists(), "PAD labels not committed")
class SkinToneAuditTests(unittest.TestCase):
    def test_the_audit_exists(self):
        self.assertTrue(
            AUDIT.exists(),
            "docs/model_cards/skin_tone_audit.md is missing. Run: "
            "python ml/audit_skin_tones.py",
        )

    def test_the_audit_covers_every_tone_in_the_dataset(self):
        if not AUDIT.exists():
            self.skipTest("audit not generated")
        with LABELS.open(encoding="utf-8") as fh:
            tones = {
                row["fitspatrick"].strip()
                for row in csv.DictReader(fh)
                if row["fitspatrick"].strip()
            }
        text = AUDIT.read_text(encoding="utf-8")
        for tone in tones:
            with self.subTest(tone=tone):
                # Roman numerals appear in the tone names of the report.
                roman = {"1": "I", "2": "II", "3": "III", "4": "IV",
                         "5": "V", "6": "VI"}[tone]
                self.assertIn(f"{roman} —", text)

    def test_the_audit_reports_both_halves(self):
        if not AUDIT.exists():
            self.skipTest("audit not generated")
        text = AUDIT.read_text(encoding="utf-8")
        self.assertIn("recall", text.lower())
        self.assertIn("রেফার", text)


if __name__ == "__main__":
    unittest.main()
