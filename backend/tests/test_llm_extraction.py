# -*- coding: utf-8 -*-
"""Tests for the LLM understanding layer.

The layer is assistive, so most of these tests are adversarial: they feed the
merge step the kind of output a confused, hallucinating or actively wrong model
would produce, and assert that the deterministic engine still governs the
outcome. A model must be able to help and must not be able to harm.

No network is used. The merge contract is tested directly, and the HTTP path is
tested against a local stub, so the suite never depends on a provider.
"""
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

os.environ["APP_ENV"] = "test"
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_llm.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from app.ai.extraction import extract  # noqa: E402
from app.ai.lexicon import SYMPTOMS  # noqa: E402
from app.ai.llm_extraction import (  # noqa: E402
    extract_with_llm,
    merge,
)


class MergeSafetyTests(unittest.TestCase):
    """The model may widen understanding. It may not overturn the rules."""

    def setUp(self):
        self.base = extract("বুকে ব্যথা, শ্বাস নিতে কষ্ট")
        self.assertIn("chest_pain", self.base.symptoms)
        self.assertIn("shortness_of_breath", self.base.symptoms)

    def test_model_cannot_remove_a_rule_matched_symptom(self):
        """The single most important guarantee: no talking away a red flag."""
        merged = merge(
            self.base,
            {"symptoms": [], "negated": ["chest_pain", "shortness_of_breath"]},
        )
        self.assertIn("chest_pain", merged.symptoms)
        self.assertIn("shortness_of_breath", merged.symptoms)

    def test_model_negation_does_not_reach_the_negated_list_either(self):
        merged = merge(self.base, {"negated": ["chest_pain"]})
        self.assertNotIn("chest_pain", merged.negated_symptoms)

    def test_invented_symptoms_are_discarded(self):
        merged = merge(
            self.base,
            {"symptoms": ["alien_disease", "heart_attack", "made_up_thing"]},
        )
        for name in merged.symptoms:
            self.assertIn(name, SYMPTOMS)

    def test_valid_new_symptoms_are_added(self):
        merged = merge(self.base, {"symptoms": ["palpitations"]})
        self.assertIn("palpitations", merged.symptoms)

    def test_model_cannot_revive_a_symptom_the_rules_saw_denied(self):
        base = extract("জ্বর নেই কিন্তু কাশি আছে")
        self.assertIn("fever", base.negated_symptoms)
        merged = merge(base, {"symptoms": ["fever"]})
        self.assertNotIn("fever", merged.symptoms)

    def test_absurd_numbers_are_rejected(self):
        merged = merge(
            self.base, {"duration_days": 99999, "age": -5, "qualifier": "apocalyptic"}
        )
        self.assertIsNone(merged.duration_days)
        self.assertIsNone(merged.age)
        self.assertIsNone(merged.qualifier)

    def test_rule_values_are_never_overwritten(self):
        base = extract("দুই দিন ধরে জ্বর, বয়স ৩০")
        merged = merge(base, {"duration_days": 500, "age": 99})
        self.assertEqual(2, merged.duration_days)
        self.assertEqual(30, merged.age)

    def test_model_fills_only_gaps(self):
        base = extract("বুকে ব্যথা")
        self.assertIsNone(base.duration_days)
        merged = merge(base, {"duration_days": 3})
        self.assertEqual(3, merged.duration_days)

    def test_malformed_output_is_survivable(self):
        for junk in ({}, {"symptoms": None}, {"symptoms": "chest_pain"},
                     {"symptoms": [None, 42, {}]}):
            with self.subTest(junk=junk):
                merged = merge(self.base, junk)
                self.assertIn("chest_pain", merged.symptoms)


class EnvFileLoadingTests(unittest.TestCase):
    """A key written to backend/.env must actually be picked up.

    The module reads os.environ, which is only populated from the file if the
    settings module has been imported. Without that import a key set in the
    file was silently ignored and the layer looked broken for no visible
    reason.
    """

    def test_importing_the_module_loads_the_env_file(self):
        import sys

        self.assertIn("app.core.config", sys.modules)


class DegradedModeTests(unittest.TestCase):
    def test_without_a_key_the_rules_run_alone(self):
        original = os.environ.pop("LLM_API_KEY", None)
        try:
            result, provenance = extract_with_llm("বুকে ব্যথা, শ্বাস নিতে কষ্ট")
            self.assertFalse(provenance["llm_used"])
            self.assertFalse(provenance["llm_available"])
            self.assertIn("chest_pain", result.symptoms)
        finally:
            if original:
                os.environ["LLM_API_KEY"] = original

    def test_an_unreachable_provider_falls_back_silently(self):
        os.environ["LLM_API_KEY"] = "test-key"
        # A port nothing is listening on.
        os.environ["LLM_API_URL"] = "http://127.0.0.1:9"
        try:
            result, provenance = extract_with_llm("বুকে ব্যথা, শ্বাস নিতে কষ্ট")
            self.assertFalse(provenance["llm_used"])
            self.assertIn("chest_pain", result.symptoms)
        finally:
            os.environ.pop("LLM_API_KEY", None)
            os.environ.pop("LLM_API_URL", None)


class _StubHandler(BaseHTTPRequestHandler):
    """Minimal OpenAI-compatible endpoint returning a fixed reading."""

    payload = {"symptoms": ["chest_pain", "weakness"], "negated": []}

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        body = json.dumps(
            {"choices": [{"message": {"content": json.dumps(self.payload)}}]}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class HttpIntegrationTests(unittest.TestCase):
    """Exercises the real request path against a local stub."""

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _StubHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        os.environ["LLM_API_KEY"] = "test-key"
        os.environ["LLM_API_URL"] = f"http://127.0.0.1:{self.port}"

    def tearDown(self):
        os.environ.pop("LLM_API_KEY", None)
        os.environ.pop("LLM_API_URL", None)

    def test_colloquial_text_the_lexicon_misses_is_understood(self):
        """The reason this layer exists: real phrasing, not dictionary forms."""
        note = "বুকটা যেন কেউ চেপে ধরছে, ঘামতেছি"
        self.assertEqual([], extract(note).symptoms)

        result, provenance = extract_with_llm(note)
        self.assertTrue(provenance["llm_used"])
        self.assertIn("chest_pain", result.symptoms)
        self.assertIn("chest_pain", provenance["llm_added_symptoms"])

    def test_provenance_separates_rule_and_model_contributions(self):
        result, provenance = extract_with_llm("বুকে ব্যথা")
        self.assertIn("chest_pain", provenance["rule_symptoms"])
        # chest_pain came from the rules, so it is not credited to the model.
        self.assertNotIn("chest_pain", provenance["llm_added_symptoms"])
        self.assertIn("weakness", provenance["llm_added_symptoms"])
        self.assertIn("weakness", result.symptoms)

    def test_a_hallucinated_response_cannot_inject_symptoms(self):
        original = _StubHandler.payload
        _StubHandler.payload = {"symptoms": ["nonexistent_symptom", "fake_illness"]}
        try:
            result, _ = extract_with_llm("বুকে ব্যথা")
            for name in result.symptoms:
                self.assertIn(name, SYMPTOMS)
        finally:
            _StubHandler.payload = original


class _JsonModeRejectingHandler(BaseHTTPRequestHandler):
    """A provider that does not understand response_format.

    Several free and self-hosted endpoints behave this way, so the client has
    to cope rather than silently losing the model.
    """

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if "response_format" in body:
            message = json.dumps(
                {"error": {"message": "Unrecognized request argument"}}
            ).encode()
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(message)))
            self.end_headers()
            self.wfile.write(message)
            return

        payload = json.dumps({"symptoms": ["chest_pain"], "negated": []})
        response = json.dumps(
            {"choices": [{"message": {"content": payload}}]}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, *args):
        pass


class DecisivePhraseTests(unittest.TestCase):
    """Phrases with only one sensible reading are settled by the rules.

    A small model occasionally picks a plausible neighbour rather than the
    right identifier. Reporting breathlessness as chest pain sends a
    respiratory patient to Cardiology, so these phrases are not left to it.
    """

    def test_breathlessness_is_not_read_as_chest_pain(self):
        from app.ai.llm_extraction import _decisive_symptoms

        found, displaced = _decisive_symptoms("niswas nite parchi na thik moto")
        self.assertIn("shortness_of_breath", found)
        self.assertIn("chest_pain", displaced)

    def test_dizziness_is_not_read_as_headache(self):
        from app.ai.llm_extraction import _decisive_symptoms

        found, displaced = _decisive_symptoms("matha ta ghurtese")
        self.assertIn("dizziness", found)
        self.assertIn("headache", displaced)

    def test_ordinary_text_is_left_to_the_model(self):
        from app.ai.llm_extraction import _decisive_symptoms

        found, displaced = _decisive_symptoms("বুকে ব্যথা")
        self.assertEqual([], found)
        self.assertEqual(set(), displaced)

    def test_a_displaced_symptom_the_rules_found_is_kept(self):
        """A lexicon match is evidence; a model guess contradicting it is not."""
        base = extract("বুকে ব্যথা")
        self.assertIn("chest_pain", base.symptoms)

        merged = merge(base, {"symptoms": ["chest_pain"]})
        from app.ai.llm_extraction import _decisive_symptoms

        _, displaced = _decisive_symptoms("বুকে ব্যথা আর niswas nite parchi na")
        # chest_pain is displaced in principle, but the rules saw it directly,
        # so it must survive and the cardiac combination must still form.
        self.assertIn("chest_pain", merged.symptoms)
        self.assertIn("chest_pain", displaced)


class UserAgentTests(unittest.TestCase):
    """A default Python user agent gets blocked by CDN-fronted providers.

    Groq returns 403 error 1010 before the request reaches the API, which is
    indistinguishable from a bad key unless a real user agent is sent.
    """

    def test_a_user_agent_is_always_sent(self):
        from app.ai.llm_extraction import USER_AGENT

        self.assertTrue(USER_AGENT)
        self.assertNotIn("urllib", USER_AGENT.lower())
        self.assertNotIn("python", USER_AGENT.lower())


class ProviderCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _JsonModeRejectingHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_retries_without_json_mode_when_the_provider_rejects_it(self):
        os.environ["LLM_API_KEY"] = "test-key"
        os.environ["LLM_API_URL"] = f"http://127.0.0.1:{self.port}"
        try:
            result, provenance = extract_with_llm("বুকটা যেন কেউ চেপে ধরছে")
            self.assertTrue(provenance["llm_used"])
            self.assertIn("chest_pain", result.symptoms)
        finally:
            os.environ.pop("LLM_API_KEY", None)
            os.environ.pop("LLM_API_URL", None)


class SafetyLayerStillGovernsTests(unittest.TestCase):
    """Red flags are decided by rules, on whatever symptoms are present."""

    def test_llm_added_symptoms_still_pass_through_the_safety_rules(self):
        from app.ai.safety import check_red_flags

        base = extract("বুকে ব্যথা")
        merged = merge(base, {"symptoms": ["shortness_of_breath"]})
        flags = check_red_flags(merged.symptoms, 55)
        self.assertIn("possible_cardiac_event", [f["flag"] for f in flags])

    def test_the_model_cannot_declare_an_emergency_by_itself(self):
        """Escalation comes from rules over symptoms, never from model text."""
        base = extract("হালকা মাথাব্যথা")
        merged = merge(
            base,
            {"symptoms": [], "severity": "EMERGENCY", "condition": "heart attack"},
        )
        from app.ai.safety import check_red_flags

        self.assertEqual([], check_red_flags(merged.symptoms, 30))


class DifferentialGuardTests(unittest.TestCase):
    """Guards added after the LLM layer surfaced weak-signal false positives."""

    def test_vague_symptoms_do_not_raise_a_stroke_alert(self):
        from app.ai.differential import differential

        results = differential(["dizziness", "blurred_vision"])
        self.assertNotIn("stroke", [r["condition"] for r in results])

    def test_focal_signs_still_identify_stroke(self):
        from app.ai.differential import differential

        results = differential(["facial_droop", "slurred_speech"])
        self.assertEqual("stroke", results[0]["condition"])

    def test_pregnancy_conditions_need_a_pregnancy_symptom(self):
        from app.ai.differential import differential

        results = differential(["abdominal_pain", "dizziness"])
        conditions = [r["condition"] for r in results]
        self.assertNotIn("obstetric_emergency", conditions)
        self.assertNotIn("possible_pregnancy", conditions)


if __name__ == "__main__":
    unittest.main()
