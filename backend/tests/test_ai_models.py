# -*- coding: utf-8 -*-
"""Tests for the BanglaMed-AI model layer.

Model tests assert on clinical behaviour and on the guarantees the safety layer
must uphold, not on exact probabilities, so retraining does not make them
brittle. Tests that need a trained artifact skip cleanly when the artifact has
not been built, which keeps a fresh clone runnable before the pipeline runs.
"""
import json
import os
import unittest
from pathlib import Path

os.environ["APP_ENV"] = "test"
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_ai.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from app.ai import features  # noqa: E402
from app.ai.drug_safety import check_interactions, normalize_drug  # noqa: E402
from app.ai.extraction import extract  # noqa: E402
from app.ai.safety import apply_safety_override, check_red_flags  # noqa: E402

ARTIFACTS = Path(__file__).resolve().parents[1] / "app" / "ai" / "artifacts"
MODEL_FILE = ARTIFACTS / "triage_model.joblib"
METRICS_FILE = ARTIFACTS / "triage_metrics.json"

# Quality gates. A retrain that regresses past these should fail the build.
MIN_MACRO_F1 = 0.75
MIN_LEVEL5_RECALL = 0.90
MAX_SEVERE_BAND_ERRORS = 5


class ExtractionTests(unittest.TestCase):
    def test_bangla_symptoms(self):
        result = extract("বুকে ব্যথা, শ্বাস নিতে কষ্ট, দুই দিন ধরে জ্বর")
        self.assertIn("chest_pain", result.symptoms)
        self.assertIn("shortness_of_breath", result.symptoms)
        self.assertIn("fever", result.symptoms)
        self.assertEqual(2, result.duration_days)

    def test_banglish_symptoms(self):
        result = extract("amar 3 din dhore matha betha r bomi hocche")
        self.assertIn("headache", result.symptoms)
        self.assertIn("vomiting", result.symptoms)
        self.assertEqual(3, result.duration_days)

    def test_code_switched_input(self):
        result = extract("High fever with শরীর ব্যথা since yesterday, বয়স ৪৫")
        self.assertIn("body_ache", result.symptoms)
        self.assertEqual(45, result.age)

    def test_negation_removes_symptom(self):
        result = extract("জ্বর নেই কিন্তু কাশি আছে এক সপ্তাহ ধরে")
        self.assertNotIn("fever", result.symptoms)
        self.assertIn("cough", result.symptoms)
        self.assertEqual(7, result.duration_days)

    def test_negation_does_not_swallow_intensifiers(self):
        """'bleeding will not stop' is more severe, not a negation."""
        result = extract("severe bleeding that will not stop")
        self.assertIn("severe_bleeding", result.symptoms)
        self.assertNotIn("severe_bleeding", result.negated_symptoms)

    def test_higher_acuity_match_wins_overlap(self):
        """'রক্ত বমি' must not be reduced to plain 'বমি'."""
        result = extract("রক্ত বমি হচ্ছে")
        self.assertIn("blood_vomiting", result.symptoms)

    def test_qualifier_detected(self):
        self.assertEqual("severe", extract("তীব্র মাথাব্যথা").qualifier)
        self.assertEqual("mild", extract("halka jor").qualifier)


class SafetyTests(unittest.TestCase):
    def test_cardiac_combination_flags(self):
        flags = check_red_flags(["chest_pain", "shortness_of_breath"], 50)
        self.assertIn("possible_cardiac_event", [f["flag"] for f in flags])

    def test_chest_pain_alone_does_not_flag(self):
        self.assertEqual([], check_red_flags(["chest_pain"], 50))

    def test_infant_fever_flags_only_for_infants(self):
        self.assertTrue(check_red_flags(["high_fever"], 0))
        self.assertFalse(check_red_flags(["high_fever"], 30))

    def test_override_only_escalates(self):
        flags = check_red_flags(["seizure"], None)
        self.assertEqual(5, apply_safety_override(1, flags))
        self.assertEqual(3, apply_safety_override(3, []))

    def test_every_red_flag_is_bilingual(self):
        from app.ai.safety import RED_FLAG_RULES

        for rule in RED_FLAG_RULES:
            self.assertTrue(rule["en"].strip(), rule["flag"])
            self.assertTrue(rule["bn"].strip(), rule["flag"])


class DrugSafetyTests(unittest.TestCase):
    def test_brand_resolves_to_generic(self):
        self.assertEqual("paracetamol", normalize_drug("Napa 500"))
        self.assertEqual("omeprazole", normalize_drug("Seclo 20 mg"))
        self.assertEqual("clopidogrel", normalize_drug("Clopid 75"))

    def test_major_interaction_detected(self):
        result = check_interactions(["Warfin", "Ecosprin"])
        self.assertEqual("major", result["highest_severity"])
        self.assertTrue(result["flagged_interactions"])

    def test_duplicate_therapy_across_brands(self):
        """Napa and Ace are both paracetamol - a real overdose route."""
        result = check_interactions(["Napa", "Ace 500"])
        effects = [f["effect"] for f in result["flagged_interactions"]]
        self.assertTrue(any("Duplicate therapy" in e for e in effects))

    def test_safe_combination_is_clean(self):
        result = check_interactions(["Napa", "Alatrol"])
        self.assertEqual([], result["flagged_interactions"])
        self.assertIsNone(result["highest_severity"])

    def test_interactions_are_bilingual(self):
        result = check_interactions(["Warfin", "Ecosprin"])
        for finding in result["flagged_interactions"]:
            self.assertTrue(finding["advice"]["en"])
            self.assertTrue(finding["advice"]["bn"])

    def test_single_drug_has_no_pairs(self):
        self.assertEqual([], check_interactions(["Napa"])["flagged_interactions"])


class ClinicalFeatureTests(unittest.TestCase):
    def test_feature_vector_length_matches_names(self):
        matrix = features.clinical_feature_matrix(
            [("বুকে ব্যথা, শ্বাস নিতে কষ্ট", 45)]
        )
        self.assertEqual((1, len(features.FEATURE_NAMES)), matrix.shape)

    def test_red_flag_feature_is_set(self):
        matrix = features.clinical_feature_matrix(
            [("বুকে ব্যথা, শ্বাস নিতে কষ্ট", 45)]
        )
        position = features.FEATURE_NAMES.index("red_flag_any")
        self.assertEqual(1.0, matrix[0][position])

    def test_age_argument_used_when_absent_from_text(self):
        matrix = features.clinical_feature_matrix([("অনেক জ্বর", 0)])
        position = features.FEATURE_NAMES.index("age_infant")
        self.assertEqual(1.0, matrix[0][position])


@unittest.skipUnless(MODEL_FILE.exists(), "triage model artifact not built")
class TriageModelTests(unittest.TestCase):
    def setUp(self):
        from app.ai.triage_service import triage

        self.triage = triage

    def test_emergency_presentation_returns_level_five(self):
        result = self.triage("বুকে ব্যথা, শ্বাস নিতে কষ্ট", age=55)
        self.assertEqual(5, result["severity_level"])
        self.assertTrue(result["safety_flags"])

    def test_mild_presentation_is_not_emergency(self):
        result = self.triage("halka matha betha", age=30)
        self.assertLess(result["severity_level"], 4)

    def test_response_contract(self):
        result = self.triage("তিন দিন ধরে জ্বর ও কাশি", age=30)
        for key in (
            "severity_level",
            "severity_label",
            "confidence_score",
            "recommended_pathway",
            "matched_specialties",
            "safety_flags",
            "entities",
            "disclaimer",
            "model_version",
        ):
            self.assertIn(key, result)
        self.assertTrue(result["disclaimer"]["bn"])
        self.assertTrue(result["disclaimer"]["en"])

    def test_confidence_within_range(self):
        result = self.triage("জ্বর", age=30)
        self.assertGreaterEqual(result["confidence_score"], 0.0)
        self.assertLessEqual(result["confidence_score"], 1.0)

    def test_safety_layer_cannot_be_undercut_by_the_model(self):
        """Whatever the classifier says, a red flag forces level 5."""
        for note, age in [
            ("সাপে কামড়েছে", 30),
            ("খিঁচুনি হচ্ছে", 25),
            ("রক্ত বমি", 40),
            ("গর্ভাবস্থায় রক্তপাত", 27),
        ]:
            with self.subTest(note=note):
                self.assertEqual(5, self.triage(note, age=age)["severity_level"])


class DegradedModeTests(unittest.TestCase):
    """Behaviour when the generated artifacts are absent.

    A bare clone must still serve the safety-critical paths, and must never
    disclose server filesystem paths in an error response.
    """

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient

        from app.main import app

        cls.client = TestClient(app, raise_server_exceptions=False)

    def test_rule_triage_works_without_any_artifact(self):
        response = self.client.post(
            "/api/v1/triage",
            json={"symptoms": "বুকে ব্যথা, শ্বাস নিতে কষ্ট", "age_years": 50},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("EMERGENCY", response.json()["triage_level"])

    def test_errors_never_leak_a_filesystem_path(self):
        for path, payload in [
            ("/api/v1/ai/triage-ml", {"symptoms": "জ্বর", "age_years": 30}),
            ("/api/v1/ai/drug-check", {"drugs": ["Napa", "Seclo"]}),
        ]:
            with self.subTest(path=path):
                body = self.client.post(path, json=payload).text
                self.assertNotIn("/home/", body)
                self.assertNotIn("/app/", body)
                self.assertNotIn(".joblib'", body)

        for path in [
            "/api/v1/hospitals/H001/surge-forecast",
            "/api/v1/population/surveillance",
        ]:
            with self.subTest(path=path):
                body = self.client.get(path).text
                self.assertNotIn("/home/", body)
                self.assertNotIn("/app/", body)
                self.assertNotIn("Errno", body)

    def test_missing_artifacts_report_503_not_404(self):
        """503 says 'not built yet'; 404 would wrongly imply 'no such hospital'."""
        if MODEL_FILE.exists():
            self.skipTest("artifacts are present")
        response = self.client.post(
            "/api/v1/ai/triage-ml", json={"symptoms": "জ্বর", "age_years": 30}
        )
        self.assertEqual(503, response.status_code)


@unittest.skipUnless(METRICS_FILE.exists(), "triage metrics not built")
class ModelQualityGateTests(unittest.TestCase):
    """Guard against a retrain silently regressing model quality."""

    def setUp(self):
        self.metrics = json.loads(METRICS_FILE.read_text())

    def test_macro_f1_above_threshold(self):
        self.assertGreaterEqual(self.metrics["test_macro_f1"], MIN_MACRO_F1)

    def test_emergency_recall_above_threshold(self):
        self.assertGreaterEqual(self.metrics["level5_recall"], MIN_LEVEL5_RECALL)

    def test_no_dangerous_band_errors(self):
        self.assertLessEqual(
            self.metrics["severe_band_errors"], MAX_SEVERE_BAND_ERRORS
        )


if __name__ == "__main__":
    unittest.main()
