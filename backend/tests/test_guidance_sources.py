"""Source retrieval must be deterministic, primary-source-only and non-advisory."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class GuidanceSourceTests(unittest.TestCase):
    def test_emergency_includes_basic_emergency_care(self):
        from app.ai.guidance_sources import retrieve_guidance_sources

        sources = retrieve_guidance_sources(
            symptoms=["shortness_of_breath"],
            safety_flags=["severe_respiratory_distress"],
        )
        self.assertEqual("who_basic_emergency_care", sources[0]["id"])
        self.assertTrue(all(source["url"].startswith("https://www.who.int/") for source in sources))

    def test_dengue_context_includes_regional_reference(self):
        from app.ai.guidance_sources import retrieve_guidance_sources

        ids = {source["id"] for source in retrieve_guidance_sources(
            symptoms=["fever", "rash"], safety_flags=[], possible_condition="Dengue"
        )}
        self.assertIn("who_dengue_primary_care", ids)
        self.assertIn("who_arboviral_guideline", ids)

    def test_every_card_says_it_is_not_treatment_advice(self):
        from app.ai.guidance_sources import retrieve_guidance_sources

        for source in retrieve_guidance_sources(symptoms=[], safety_flags=[]):
            self.assertIn("not patient-specific treatment advice", source["retrieval_note"])


if __name__ == "__main__":
    unittest.main()
