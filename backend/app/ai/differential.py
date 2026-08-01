# -*- coding: utf-8 -*-
"""Differential reasoning: ranking likely conditions from extracted symptoms.

This is deliberately a transparent scoring model rather than a learned one.
A patient — and more importantly a reviewing clinician — can be shown exactly
which symptoms drove each suggestion, which is not possible with an opaque
classifier and matters more here than a marginal accuracy gain.

Scoring, per condition:

    score = Σ(weight of each matched supporting symptom)
          × coverage factor      how much of the condition's picture is present
          × prior                baseline plausibility in Bangladesh
          × seasonal multiplier  dengue in monsoon, flu in winter
          × duration factor      TB needs a cough lasting weeks, not days
          − excluding penalty    symptoms that argue against it

Scores are then normalised across the surviving candidates so the output reads
as relative likelihood. It is never presented as a diagnosis, and the wording
in every response says so.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .conditions import CONDITIONS, SEASONAL_PRIOR

# Below this share of the top score a candidate is dropped, unless it is a
# red-flag condition.
RELATIVE_CUTOFF = 0.25

# A red-flag condition is always shown once it has any real support, because
# the cost of omitting it is not symmetric with the cost of listing it.
RED_FLAG_MIN_SCORE = 1.5

MAX_RESULTS = 5


def _seasonal_multiplier(condition_key: str, month: Optional[int]) -> float:
    if month is None:
        return 1.0
    return SEASONAL_PRIOR.get(condition_key, {}).get(month, 1.0)


def _duration_factor(entry: dict, duration_days: Optional[int]) -> float:
    """Some conditions are defined partly by how long symptoms have lasted."""
    minimum = entry.get("duration_days_min")
    if minimum is None:
        return 1.0
    if duration_days is None:
        # Duration unknown: neither reward nor heavily penalise.
        return 0.85
    if duration_days >= minimum:
        return 1.6
    # Present but too recent to fit the pattern.
    return 0.3


def _score_condition(
    key: str,
    entry: dict,
    symptoms: set[str],
    duration_days: Optional[int],
    month: Optional[int],
) -> Optional[dict]:
    required = entry.get("required") or []
    if required and not any(name in symptoms for name in required):
        return None

    supporting = entry.get("supporting", {})
    matched = {name: w for name, w in supporting.items() if name in symptoms}
    if not matched:
        return None

    raw = sum(matched.values())

    # Coverage rewards a condition whose full picture is present over one that
    # merely shares a single common symptom. Square-rooted so that a broad
    # condition is not unfairly penalised for having many optional features.
    total_weight = sum(supporting.values()) or 1.0
    coverage = (raw / total_weight) ** 0.5

    excluding = entry.get("excluding") or []
    contradictions = [name for name in excluding if name in symptoms]
    penalty = 0.55 ** len(contradictions)

    score = (
        raw
        * coverage
        * entry.get("prior", 1.0)
        * _seasonal_multiplier(key, month)
        * _duration_factor(entry, duration_days)
        * penalty
    )

    return {
        "key": key,
        "score": score,
        "matched": sorted(matched, key=lambda n: -matched[n]),
        "contradicted_by": contradictions,
        "is_red_flag": bool(entry.get("red_flag")),
    }


def differential(
    symptoms: list[str],
    duration_days: Optional[int] = None,
    age: Optional[int] = None,
    now: Optional[datetime] = None,
) -> list[dict]:
    """Rank plausible conditions for a set of extracted symptoms."""
    if not symptoms:
        return []

    symptom_set = set(symptoms)
    month = (now or datetime.now(timezone.utc)).month

    scored = []
    for key, entry in CONDITIONS.items():
        result = _score_condition(key, entry, symptom_set, duration_days, month)
        if result:
            scored.append(result)

    if not scored:
        return []

    scored.sort(key=lambda item: -item["score"])
    top = scored[0]["score"]

    # Surface the most time-critical red flag first when several are close in
    # score. A patient scanning the list should not have to read to the bottom
    # to find the possibility that would kill them.
    def display_order(item):
        entry = CONDITIONS[item["key"]]
        acuity = entry.get("acuity", 9) if item["is_red_flag"] else 9
        return (acuity, -item["score"])

    scored.sort(key=display_order)

    kept = []
    for item in scored:
        relative = item["score"] / top if top else 0.0
        is_significant = relative >= RELATIVE_CUTOFF
        is_notable_red_flag = item["is_red_flag"] and item["score"] >= RED_FLAG_MIN_SCORE

        if is_significant or is_notable_red_flag:
            kept.append((item, relative))

    kept = kept[:MAX_RESULTS]

    # Normalise across what survived so the reported confidence reflects the
    # choice actually being presented.
    total = sum(item["score"] for item, _ in kept) or 1.0

    output = []
    for item, relative in kept:
        entry = CONDITIONS[item["key"]]
        output.append(
            {
                "condition": item["key"],
                "name_en": entry["en"],
                "name_bn": entry["bn"],
                "specialty": entry["specialty"],
                "likelihood": round(item["score"] / total, 3),
                "relative_to_top": round(relative, 3),
                "matched_symptoms": item["matched"],
                "contradicted_by": item["contradicted_by"],
                "is_red_flag": item["is_red_flag"],
                "acuity": entry.get("acuity", 9),
                "advice_en": entry.get("advice_en", ""),
                "advice_bn": entry.get("advice_bn", ""),
            }
        )
    return output


def recommended_specialty(results: list[dict]) -> Optional[str]:
    """Specialty to route to.

    A red-flag condition decides the referral even when a benign condition
    scores higher: the cost of routing a possible heart attack to a general
    physician is not comparable to the cost of the reverse.

    Where several red flags are plausible — chest pain with breathlessness
    fits both a heart attack and an asthma attack — the most time-critical one
    wins the referral regardless of which scored higher. Likelihood is the
    wrong tiebreaker when the outcomes differ by this much.
    """
    if not results:
        return None

    red_flags = [item for item in results if item["is_red_flag"]]
    if red_flags:
        red_flags.sort(key=lambda item: (item["acuity"], -item["likelihood"]))
        return red_flags[0]["specialty"]

    return results[0]["specialty"]
