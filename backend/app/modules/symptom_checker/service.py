import unicodedata

from app.modules.symptom_checker.rules import (
    CONDITION_RULES,
    EMERGENCY_RULES,
    SEVERITY_PRIORITY,
)
from app.schemas.symptom_checker import SymptomResponse
from app.schemas.triage import TriageLevel, TriageRequest, TriageResponse


CLINICAL_DISCLAIMER = (
    "This result is decision support, not a diagnosis. If symptoms are severe "
    "or worsening, seek care from a qualified healthcare professional."
)


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _keyword_groups(rule: dict, language: str) -> list[list[str]]:
    if language == "bn":
        return [[keyword] for keyword in rule["bangla"]]
    if language == "en":
        return [[keyword] for keyword in rule["english"]]

    group_count = max(len(rule["bangla"]), len(rule["english"]))
    groups = []
    for index in range(group_count):
        alternatives = []
        if index < len(rule["bangla"]):
            alternatives.append(rule["bangla"][index])
        if index < len(rule["english"]):
            alternatives.append(rule["english"][index])
        groups.append(alternatives)
    return groups


def _matched_keywords(text: str, groups: list[list[str]]) -> list[str]:
    matched = []
    for alternatives in groups:
        match = next(
            (
                keyword
                for keyword in alternatives
                if _normalize(keyword) in text
            ),
            None,
        )
        if match:
            matched.append(match)
    return matched


def _rule_matches(rule: dict, matched: list[str], group_count: int) -> bool:
    if rule["match"] == "all":
        return group_count > 0 and len(matched) == group_count
    return bool(matched)


def _confidence(rule: dict, matched_count: int, keyword_count: int) -> int:
    if keyword_count == 0:
        return 0
    coverage = matched_count / keyword_count
    if rule["match"] == "all":
        return min(95, round(75 + (20 * coverage)))
    return min(90, round(55 + (35 * coverage)))


def triage_symptoms(request: TriageRequest) -> TriageResponse:
    text = _normalize(request.symptoms)

    for rule in EMERGENCY_RULES:
        groups = _keyword_groups(rule, request.language)
        matched = _matched_keywords(text, groups)
        if _rule_matches(rule, matched, len(groups)):
            return TriageResponse(
                triage_level=TriageLevel.EMERGENCY,
                possible_condition=rule["condition"],
                recommended_specialty=rule["specialty"],
                confidence=99,
                matched_symptoms=matched,
                safety_flags=[rule["code"]],
                advice=rule["advice"],
                disclaimer=CLINICAL_DISCLAIMER,
            )

    candidates = []
    for rule in CONDITION_RULES:
        groups = _keyword_groups(rule, request.language)
        matched = _matched_keywords(text, groups)
        if _rule_matches(rule, matched, len(groups)):
            candidates.append(
                (
                    SEVERITY_PRIORITY[rule["severity"]],
                    len(matched),
                    rule,
                    matched,
                    len(groups),
                )
            )

    if not candidates:
        return TriageResponse(
            triage_level=TriageLevel.TELECONSULT,
            possible_condition="Symptoms need clinical review",
            recommended_specialty="General Physician",
            confidence=0,
            matched_symptoms=[],
            safety_flags=[],
            advice="Book a consultation for a proper clinical assessment.",
            disclaimer=CLINICAL_DISCLAIMER,
        )

    _, _, rule, matched, keyword_count = max(
        candidates,
        key=lambda candidate: (candidate[0], candidate[1]),
    )
    return TriageResponse(
        triage_level=TriageLevel(rule["severity"]),
        possible_condition=rule["condition"],
        recommended_specialty=rule["specialty"],
        confidence=_confidence(rule, len(matched), keyword_count),
        matched_symptoms=matched,
        safety_flags=[],
        advice=rule["advice"],
        disclaimer=CLINICAL_DISCLAIMER,
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
