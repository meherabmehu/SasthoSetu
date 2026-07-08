import unittest

from pydantic import ValidationError

from app.modules.symptom_checker.service import triage_symptoms
from app.schemas.triage import TriageLevel, TriageRequest


class TriageServiceTests(unittest.TestCase):
    def test_cardiorespiratory_combination_is_emergency(self):
        result = triage_symptoms(
            TriageRequest(
                symptoms="I have chest pain and shortness of breath",
                language="en",
            )
        )

        self.assertEqual(result.triage_level, TriageLevel.EMERGENCY)
        self.assertIn("CARDIO_RESPIRATORY_DISTRESS", result.safety_flags)

    def test_single_chest_pain_does_not_trigger_combination_rule(self):
        result = triage_symptoms(
            TriageRequest(symptoms="I have chest pain", language="en")
        )

        self.assertNotEqual(result.triage_level, TriageLevel.EMERGENCY)

    def test_bangla_emergency_rule(self):
        result = triage_symptoms(
            TriageRequest(
                symptoms="আমার বুকে ব্যথা এবং শ্বাসকষ্ট হচ্ছে",
                language="bn",
            )
        )

        self.assertEqual(result.triage_level, TriageLevel.EMERGENCY)

    def test_dengue_rule_requires_both_symptoms(self):
        result = triage_symptoms(
            TriageRequest(
                symptoms="দুই দিন ধরে জ্বর এবং শরীর ব্যথা",
                language="bn",
            )
        )

        self.assertEqual(result.triage_level, TriageLevel.SPECIALIST)
        self.assertIn("dengue", result.possible_condition.lower())

    def test_mixed_language_input_is_supported_in_auto_mode(self):
        result = triage_symptoms(
            TriageRequest(symptoms="জ্বর with body pain")
        )

        self.assertEqual(result.triage_level, TriageLevel.SPECIALIST)

    def test_unknown_symptoms_fall_back_to_teleconsult(self):
        result = triage_symptoms(
            TriageRequest(symptoms="I feel unusually tired after work")
        )

        self.assertEqual(result.triage_level, TriageLevel.TELECONSULT)
        self.assertEqual(result.confidence, 0)

    def test_non_descriptive_input_is_rejected(self):
        with self.assertRaises(ValidationError):
            TriageRequest(symptoms="12345")


if __name__ == "__main__":
    unittest.main()
