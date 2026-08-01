# -*- coding: utf-8 -*-
"""Deterministic bilingual triage service.

Pipeline:

    raw note -> lexicon entity extraction -> red-flag safety check
             -> condition rules -> triage response

Symptom recognition uses the shared BanglaMed-AI lexicon, so Bangla
("শ্বাস নিতে কষ্ট"), Banglish ("shash nite koshto") and English
("breathing difficulty") phrasings of the same complaint all resolve to the
same canonical symptom. Emergency escalation comes from the single red-flag
table in ``app.ai.safety`` and can only raise severity, never lower it.
"""
from typing import Optional

from app.ai.differential import differential as build_differential
from app.ai.differential import recommended_specialty
from app.ai.extraction import extract
from app.ai.lexicon import SYMPTOMS
from app.ai.safety import check_red_flags
from app.modules.symptom_checker.rules import (
    CONDITION_RULES,
    LEVEL_TO_SEVERITY,
    SEVERITY_PRIORITY,
)
from app.schemas.symptom_checker import SymptomResponse
from app.schemas.triage import TriageLevel, TriageRequest, TriageResponse


CLINICAL_DISCLAIMER = (
    "This result is decision support, not a diagnosis. If symptoms are severe "
    "or worsening, seek care from a qualified healthcare professional."
)

CLINICAL_DISCLAIMER_BN = (
    "এই ফলাফল সিদ্ধান্ত-সহায়ক তথ্য, কোনো রোগ নির্ণয় নয়। উপসর্গ তীব্র হলে বা "
    "বাড়তে থাকলে দ্রুত রেজিস্টার্ড চিকিৎসকের পরামর্শ নিন।"
)

EMERGENCY_ADVICE = (
    "Go to the nearest hospital emergency department now, or call an ambulance."
)
EMERGENCY_ADVICE_BN = (
    "এখনই নিকটস্থ হাসপাতালের জরুরি বিভাগে যান অথবা অ্যাম্বুলেন্স ডাকুন।"
)

FEVER_EMERGENCY_TEMP_C = 40.0


def _readable(symptom_id: str) -> str:
    """Human-readable label for a canonical symptom id."""
    entry = SYMPTOMS.get(symptom_id)
    if entry and entry["en"]:
        return entry["en"][0]
    return symptom_id.replace("_", " ")


def _specialty_for(symptom_ids: list[str]) -> str:
    """Highest-acuity symptom decides the specialty."""
    ranked = sorted(
        symptom_ids,
        key=lambda s: SYMPTOMS[s]["level"] if s in SYMPTOMS else 0,
        reverse=True,
    )
    for symptom_id in ranked:
        entry = SYMPTOMS.get(symptom_id)
        if entry:
            return entry["specialty"]
    return "General Physician"


def _rule_matches(rule: dict, found: set) -> list[str]:
    matched = [s for s in rule["symptoms"] if s in found]
    if rule["match"] == "all":
        return matched if len(matched) == len(rule["symptoms"]) else []
    return matched


def _confidence(rule: dict, matched_count: int) -> int:
    total = len(rule["symptoms"])
    if total == 0:
        return 0
    coverage = matched_count / total
    if rule["match"] == "all":
        return min(95, round(75 + (20 * coverage)))
    return min(90, round(55 + (35 * coverage)))


def _baseline_from_lexicon(found: list[str]) -> Optional[int]:
    """Fallback severity: the highest base level among recognised symptoms."""
    levels = [SYMPTOMS[s]["level"] for s in found if s in SYMPTOMS]
    return max(levels) if levels else None


def triage_symptoms(request: TriageRequest) -> TriageResponse:
    result = extract(request.symptoms)
    age = request.age_years if request.age_years is not None else result.age
    found = result.symptoms
    found_set = set(found)

    # Likely conditions, ranked. Independent of the urgency decision below:
    # urgency stays deterministic, the differential is advisory.
    conditions = build_differential(
        found, duration_days=result.duration_days, age=age
    )

    # ---- Safety layer: red flags always win -----------------------------
    flags = check_red_flags(found, age)

    if (
        request.temperature_c is not None
        and request.temperature_c >= FEVER_EMERGENCY_TEMP_C
    ):
        flags = flags + [
            {
                "flag": "hyperpyrexia",
                "en": "Measured temperature at or above 40°C",
                "bn": "মাপা তাপমাত্রা ৪০ ডিগ্রি সেলসিয়াস বা তার বেশি",
            }
        ]

    if flags:
        return TriageResponse(
            triage_level=TriageLevel.EMERGENCY,
            possible_condition=flags[0]["en"],
            possible_condition_bn=flags[0]["bn"],
            recommended_specialty="Emergency Medicine",
            confidence=99,
            matched_symptoms=[_readable(s) for s in found],
            safety_flags=[f["flag"] for f in flags],
            differential=conditions,
            advice=EMERGENCY_ADVICE,
            advice_bn=EMERGENCY_ADVICE_BN,
            disclaimer=CLINICAL_DISCLAIMER,
            disclaimer_bn=CLINICAL_DISCLAIMER_BN,
        )

    # ---- Condition rules -------------------------------------------------
    candidates = []
    for rule in CONDITION_RULES:
        matched = _rule_matches(rule, found_set)
        if matched:
            candidates.append((SEVERITY_PRIORITY[rule["severity"]], len(matched), rule, matched))

    if candidates:
        _, _, rule, matched = max(candidates, key=lambda c: (c[0], c[1]))
        severity = rule["severity"]

        # A recognised symptom with a higher base acuity than the matched rule
        # escalates the outcome; triage never under-calls a known symptom.
        baseline = _baseline_from_lexicon(found)
        if baseline and baseline > SEVERITY_PRIORITY[severity]:
            severity = LEVEL_TO_SEVERITY[baseline]

        # A named condition from the differential is more useful to a patient
        # than a rule label like "Fever requiring assessment", but only when
        # the differential is actually confident about it.
        top = conditions[0] if conditions else None
        use_differential = bool(top and top["likelihood"] >= 0.45)

        condition_en = top["name_en"] if use_differential else rule["condition"]
        condition_bn = top["name_bn"] if use_differential else rule["condition_bn"]

        referral = recommended_specialty(conditions) if conditions else None
        if not referral:
            referral = (
                _specialty_for(found)
                if severity != rule["severity"]
                else rule["specialty"]
            )

        return TriageResponse(
            triage_level=TriageLevel(severity),
            possible_condition=condition_en,
            possible_condition_bn=condition_bn,
            recommended_specialty=referral,
            confidence=_confidence(rule, len(matched)),
            matched_symptoms=[_readable(s) for s in found],
            safety_flags=[],
            differential=conditions,
            advice=rule["advice"],
            advice_bn=rule["advice_bn"],
            disclaimer=CLINICAL_DISCLAIMER,
            disclaimer_bn=CLINICAL_DISCLAIMER_BN,
        )

    # ---- Recognised symptoms but no rule: use lexicon acuity -------------
    baseline = _baseline_from_lexicon(found)
    if baseline:
        severity = LEVEL_TO_SEVERITY[baseline]
        return TriageResponse(
            triage_level=TriageLevel(severity),
            possible_condition=(
                conditions[0]["name_en"]
                if conditions
                else "Symptoms require clinical assessment"
            ),
            possible_condition_bn=(
                conditions[0]["name_bn"]
                if conditions
                else "উপসর্গগুলোর জন্য চিকিৎসকের মূল্যায়ন প্রয়োজন"
            ),
            recommended_specialty=(
                recommended_specialty(conditions) or _specialty_for(found)
            ),
            confidence=60,
            matched_symptoms=[_readable(s) for s in found],
            safety_flags=[],
            differential=conditions,
            advice="Book a consultation with the recommended specialty.",
            advice_bn="প্রস্তাবিত বিভাগের চিকিৎসকের সাথে পরামর্শের জন্য বুকিং দিন।",
            disclaimer=CLINICAL_DISCLAIMER,
            disclaimer_bn=CLINICAL_DISCLAIMER_BN,
        )

    # ---- Nothing recognised: safe fallback -------------------------------
    return TriageResponse(
        triage_level=TriageLevel.TELECONSULT,
        possible_condition="Symptoms need clinical review",
        possible_condition_bn="উপসর্গগুলোর জন্য চিকিৎসকের পর্যালোচনা প্রয়োজন",
        recommended_specialty="General Physician",
        confidence=0,
        matched_symptoms=[],
        safety_flags=[],
        advice="Book a consultation for a proper clinical assessment.",
        advice_bn="সঠিক মূল্যায়নের জন্য একজন চিকিৎসকের পরামর্শ নিন।",
        disclaimer=CLINICAL_DISCLAIMER,
        disclaimer_bn=CLINICAL_DISCLAIMER_BN,
    )


def analyze_symptoms_service(symptoms: str) -> SymptomResponse:
    """Compatibility adapter for the original /symptom-checker endpoint."""
    result = triage_symptoms(TriageRequest(symptoms=symptoms))
    return SymptomResponse(
        severity=result.triage_level.value,
        possible_disease=result.possible_condition,
        recommended_specialist=result.recommended_specialty,
        confidence=result.confidence,
        recommendation=result.advice,
    )
