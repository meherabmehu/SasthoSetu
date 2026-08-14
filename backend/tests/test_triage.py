# -*- coding: utf-8 -*-
"""Triage safety and behaviour tests.

The red-flag matrix below is deliberately adversarial: every emergency
presentation is expressed in natural Bangla, romanised Banglish, plain English
and an English paraphrase. A red flag that only fires on one phrasing is a
clinical defect, not a cosmetic one.
"""
import os
import unittest

os.environ["APP_ENV"] = "test"
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_triage.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from app.modules.symptom_checker.service import (  # noqa: E402
    analyze_symptoms_service,
    triage_symptoms,
)
from app.schemas.triage import TriageLevel, TriageRequest  # noqa: E402


def run(symptoms, **kwargs):
    return triage_symptoms(TriageRequest(symptoms=symptoms, **kwargs))


# (label, [phrasings]) - every phrasing must return EMERGENCY
RED_FLAG_MATRIX = [
    (
        "cardiac: chest pain + breathlessness",
        [
            "বুকে ব্যথা, শ্বাস নিতে কষ্ট",
            "বুকে ব্যথা এবং শ্বাসকষ্ট হচ্ছে",
            "buke betha ar shash nite koshto",
            "chest pain and shortness of breath",
            "chest pain with breathing difficulty",
            "chest pain, difficulty breathing",
            "chest pain and trouble breathing",
            "chest pain, hard to breathe",
            "I have chest pressure and cant breathe properly",
        ],
    ),
    (
        "altered consciousness",
        [
            "রোগী অজ্ঞান হয়ে গেছে",
            "rogi oggan hoye gese",
            "patient is unconscious",
        ],
    ),
    (
        "severe bleeding",
        [
            "প্রচণ্ড রক্তপাত হচ্ছে",
            "prochondo roktopat hocche",
            "severe bleeding that will not stop",
        ],
    ),
    (
        "meningitis: fever + stiff neck",
        [
            "তীব্র জ্বর আর ঘাড় শক্ত হয়ে গেছে",
            "onek jor ar ghar shokto",
            "high fever with stiff neck",
        ],
    ),
    (
        "stroke (FAST)",
        [
            "মুখ বেঁকে গেছে, কথা জড়িয়ে যাচ্ছে",
            "kotha jorano ar ek pash obosh",
            "facial droop and slurred speech",
        ],
    ),
    (
        "seizure",
        ["খিঁচুনি হচ্ছে", "khichuni hocche", "having convulsions"],
    ),
    (
        "haematemesis",
        ["রক্ত বমি হচ্ছে", "rokto bomi", "vomiting blood"],
    ),
    (
        "obstetric bleeding",
        [
            "গর্ভাবস্থায় রক্তপাত",
            "গর্ভবতী অবস্থায় রক্তপাত হচ্ছে",
            "bleeding during pregnancy",
        ],
    ),
    (
        "snake bite",
        ["সাপে কামড়েছে", "shape kamor", "snake bite"],
    ),
    # Phrasings that a real user typed and the matcher missed.
    (
        "haematemesis written as one word",
        ["রক্তবমি হচ্ছে", "roktobomi hocche", "বমিতে রক্ত"],
    ),
    (
        "meningism without a reported fever",
        [
            "প্রচণ্ড মাথাব্যথা এবং ঘাড় শক্ত",
            "তীব্র মাথাব্যথা ও ঘাড় শক্ত",
            "stiff neck and severe headache",
        ],
    ),
    (
        "cardiac chest pain with sweating",
        [
            "bukey betha, ghamtesi",
            "বুকে ব্যথা আর ঘামছি",
            "chest pain and cold sweat",
        ],
    ),
    (
        "cannot breathe",
        [
            "niswas nite parchi na",
            "শ্বাস নিতে পারছি না",
            "shash nite parchi na",
        ],
    ),
]


class RedFlagMatrixTests(unittest.TestCase):
    """Every emergency phrasing must escalate, in every language."""

    def test_red_flags_escalate_in_every_phrasing(self):
        failures = []
        for label, phrasings in RED_FLAG_MATRIX:
            for phrasing in phrasings:
                result = run(phrasing)
                if result.triage_level is not TriageLevel.EMERGENCY:
                    failures.append(
                        f"{label!r} / {phrasing!r} -> {result.triage_level.value}"
                    )
        self.assertEqual([], failures, "red flags missed:\n" + "\n".join(failures))

    def test_red_flag_responses_carry_a_safety_flag(self):
        for label, phrasings in RED_FLAG_MATRIX:
            with self.subTest(label=label):
                result = run(phrasings[0])
                self.assertTrue(result.safety_flags, f"{label} has no safety flag")
                self.assertEqual("Emergency Medicine", result.recommended_specialty)

    def test_infant_high_fever_is_an_emergency(self):
        self.assertIs(
            TriageLevel.EMERGENCY, run("বাচ্চার অনেক জ্বর", age_years=0).triage_level
        )

    def test_same_fever_in_an_adult_is_not_an_emergency(self):
        self.assertIsNot(
            TriageLevel.EMERGENCY, run("অনেক জ্বর", age_years=30).triage_level
        )

    def test_measured_hyperpyrexia_escalates(self):
        result = run("জ্বর", temperature_c=40.5)
        self.assertIs(TriageLevel.EMERGENCY, result.triage_level)
        self.assertIn("hyperpyrexia", result.safety_flags)


class EvidenceThresholdTests(unittest.TestCase):
    """A serious condition needs more than one everyday symptom.

    "পেট ব্যথা" alone produced a possible-appendicitis headline at 25% while a
    peptic ulcer sat below it at 39%. Abdominal pain fits appendicitis, an
    ulcer, typhoid and ordinary indigestion equally well, so naming the
    surgical one alarms the patient without telling them anything.
    """

    def test_one_ordinary_symptom_does_not_raise_a_surgical_emergency(self):
        from app.ai.differential import differential

        keys = [item["condition"] for item in differential(["abdominal_pain"])]
        self.assertNotIn("appendicitis", keys)
        self.assertIn("peptic_ulcer", keys)

    def test_a_second_feature_brings_it_back(self):
        from app.ai.differential import differential

        keys = [
            item["condition"]
            for item in differential(["abdominal_pain", "vomiting"])
        ]
        self.assertIn("appendicitis", keys)

    def test_a_single_alarming_symptom_still_raises_its_red_flag(self):
        """Chest pain is not abdominal pain: the symptom itself is the warning."""
        from app.ai.differential import differential

        keys = [item["condition"] for item in differential(["chest_pain"])]
        self.assertIn("acute_coronary_syndrome", keys)

        keys = [item["condition"] for item in differential(["shortness_of_breath"])]
        self.assertIn("asthma_exacerbation", keys)

    def test_the_headline_is_the_most_likely_condition(self):
        result = run("পেট ব্যথা", age_years=30)

        top = max(result.differential, key=lambda item: item["likelihood"])
        self.assertEqual(top["name_en"], result.possible_condition)

    def test_the_headline_never_understates_a_red_flag_result(self):
        """Ordering the headline by likelihood must not soften an emergency."""
        result = run("বুকে ব্যথা, শ্বাস নিতে কষ্ট", age_years=55)

        self.assertIs(TriageLevel.EMERGENCY, result.triage_level)
        self.assertEqual("Emergency Medicine", result.recommended_specialty)


class TemperatureUnitTests(unittest.TestCase):
    """Thermometers in Bangladesh are marked in Fahrenheit.

    The field accepted only Celsius, so the natural reading of "101" was
    rejected with "Input should be less than or equal to 45" — a message that
    never mentions a unit and leaves the reader guessing.
    """

    def test_a_fahrenheit_reading_is_converted(self):
        from app.schemas.triage import TriageRequest

        self.assertEqual(
            38.3, TriageRequest(symptoms="জ্বর", temperature_c=101).temperature_c
        )
        self.assertEqual(
            37.0, TriageRequest(symptoms="জ্বর", temperature_c=98.6).temperature_c
        )

    def test_a_celsius_reading_is_left_alone(self):
        from app.schemas.triage import TriageRequest

        self.assertEqual(
            38.5, TriageRequest(symptoms="জ্বর", temperature_c=38.5).temperature_c
        )

    def test_a_high_fahrenheit_fever_still_escalates(self):
        # 104 F is 40 C, which is the hyperpyrexia threshold. The conversion
        # must not lose the escalation.
        result = run("জ্বর", temperature_c=104)
        self.assertIs(TriageLevel.EMERGENCY, result.triage_level)
        self.assertIn("hyperpyrexia", result.safety_flags)

    def test_an_ordinary_fahrenheit_fever_does_not_escalate(self):
        result = run("জ্বর", temperature_c=101)
        self.assertIsNot(TriageLevel.EMERGENCY, result.triage_level)

    def test_impossible_readings_are_still_rejected(self):
        from pydantic import ValidationError

        from app.schemas.triage import TriageRequest

        for value in (200, 50, 10, -5, "abc"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    TriageRequest(symptoms="জ্বর", temperature_c=value)

    def test_the_message_names_both_units(self):
        from pydantic import ValidationError

        from app.schemas.triage import TriageRequest

        with self.assertRaises(ValidationError) as caught:
            TriageRequest(symptoms="জ্বর", temperature_c=200)

        message = caught.exception.errors()[0]["msg"]
        self.assertIn("°C", message)
        self.assertIn("°F", message)


class TriageServiceTests(unittest.TestCase):
    def test_cardiorespiratory_combination_is_emergency(self):
        result = run("chest pain and shortness of breath")
        self.assertIs(TriageLevel.EMERGENCY, result.triage_level)
        self.assertIn("possible_cardiac_event", result.safety_flags)

    def test_bangla_emergency_rule(self):
        result = run("বুকে ব্যথা এবং শ্বাসকষ্ট")
        self.assertIs(TriageLevel.EMERGENCY, result.triage_level)

    def test_single_chest_pain_does_not_trigger_combination_rule(self):
        result = run("বুকে ব্যথা")
        self.assertIsNot(TriageLevel.EMERGENCY, result.triage_level)
        self.assertEqual([], result.safety_flags)

    def test_dengue_rule_requires_both_symptoms(self):
        result = run("জ্বর এবং শরীর ব্যথা")
        self.assertIs(TriageLevel.SPECIALIST, result.triage_level)

    def test_mixed_language_input_is_supported_in_auto_mode(self):
        result = run("High fever with শরীর ব্যথা since yesterday")
        self.assertIn(
            result.triage_level, (TriageLevel.SPECIALIST, TriageLevel.GP_VISIT)
        )

    def test_unknown_symptoms_fall_back_to_teleconsult(self):
        result = run("something feels unusual today")
        self.assertIs(TriageLevel.TELECONSULT, result.triage_level)
        self.assertEqual(0, result.confidence)

    def test_non_descriptive_input_is_rejected(self):
        with self.assertRaises(ValueError):
            run("12345")

    def test_negated_symptom_is_not_matched(self):
        result = run("জ্বর নেই কিন্তু হালকা কাশি আছে")
        self.assertIsNot(TriageLevel.EMERGENCY, result.triage_level)
        self.assertNotIn("fever", result.matched_symptoms)

    def test_absence_and_inability_are_told_apart(self):
        """"হচ্ছে না" reports absence; "পারছি না" reports an inability.

        Both end in the same particle, so treating every trailing "না" as a
        negation would discard someone saying they cannot breathe.
        """
        from app.ai.extraction import extract

        absent = [
            "শ্বাস নিতে কষ্ট হচ্ছে না",
            "বমি হচ্ছে না",
            "জ্বর হচ্ছে না",
            "শ্বাসকষ্ট নেই",
        ]
        for text in absent:
            with self.subTest(text=text):
                self.assertEqual([], extract(text).symptoms)

        present = {
            "শ্বাস নিতে পারছি না": "shortness_of_breath",
            "দম নিতে পারছি না": "shortness_of_breath",
            "রক্ত বন্ধ হচ্ছে না": "severe_bleeding",
        }
        for text, symptom in present.items():
            with self.subTest(text=text):
                self.assertIn(symptom, extract(text).symptoms)

    def test_dizziness_is_recognised_in_common_phrasings(self):
        from app.ai.extraction import extract

        for text in ("মাথা ঘুরছে", "মাথা ঘোরা", "matha ta ghurtese"):
            with self.subTest(text=text):
                self.assertIn("dizziness", extract(text).symptoms)

    def test_response_is_bilingual(self):
        result = run("বুকে ব্যথা, শ্বাস নিতে কষ্ট")
        self.assertTrue(result.advice_bn)
        self.assertTrue(result.disclaimer_bn)
        self.assertTrue(result.possible_condition_bn)

    def test_severity_never_below_highest_recognised_symptom(self):
        result = run("কাশি এবং বুকে ব্যথা")
        self.assertGreaterEqual(
            ["SELF_CARE", "TELECONSULT", "GP_VISIT", "SPECIALIST", "EMERGENCY"].index(
                result.triage_level.value
            ),
            3,
        )

    def test_compatibility_adapter_returns_expected_shape(self):
        result = analyze_symptoms_service("জ্বর এবং শরীর ব্যথা")
        self.assertEqual("SPECIALIST", result.severity)
        self.assertTrue(result.recommended_specialist)


if __name__ == "__main__":
    unittest.main()
