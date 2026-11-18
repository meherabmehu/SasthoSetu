"""Regression checks for the clearly-labelled historical dengue source."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class HistoricalDengueTests(unittest.TestCase):
    def test_default_source_is_historical_real_dengue(self):
        from app.ai.surveillance_service import surveillance

        result = surveillance(disease="dengue", weeks=1)
        self.assertEqual("bangladesh_dengue_estimates_2022_2024", result["data_source"])
        self.assertFalse(result["is_live"])

    def test_historical_source_is_not_live_and_has_eight_divisions(self):
        from app.ai.surveillance_service import surveillance

        result = surveillance(
            source="bangladesh_dengue_estimates_2022_2024",
            disease="dengue",
            weeks=12,
        )
        self.assertEqual("bangladesh_dengue_estimates_2022_2024", result["data_source"])
        self.assertFalse(result["is_live"])
        self.assertTrue(result["not_for_real_time_alerting"])
        self.assertEqual("division", result["geographic_level"])
        self.assertEqual(8, len(result["series"]))
        self.assertEqual({"start": "2022-01-01", "end": "2024-12-31"}, result["coverage"])

    def test_historical_source_rejects_other_diseases(self):
        from app.ai.surveillance_service import surveillance

        with self.assertRaisesRegex(ValueError, "dengue estimates only"):
            surveillance(
                source="bangladesh_dengue_estimates_2022_2024",
                disease="malaria",
            )


if __name__ == "__main__":
    unittest.main()
