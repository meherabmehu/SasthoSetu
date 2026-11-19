"""Curated retrieval of public clinical-reference metadata.

This is intentionally a narrow, auditable retrieval layer rather than an LLM
that paraphrases treatment guidance. It returns source cards for clinician
review after the deterministic triage decision has already been made.
"""
from __future__ import annotations


_SOURCES = {
    "who_basic_emergency_care": {
        "id": "who_basic_emergency_care",
        "title": "WHO-ICRC Basic Emergency Care: approach to the acutely ill and injured",
        "publisher": "World Health Organization and International Committee of the Red Cross",
        "year": 2018,
        "url": "https://www.who.int/publications/i/item/9789241513081",
        "scope": "First-contact assessment and referral of acute illness and injury in resource-limited settings.",
    },
    "who_emergency_care_toolkit": {
        "id": "who_emergency_care_toolkit",
        "title": "WHO Emergency Care Toolkit",
        "publisher": "World Health Organization",
        "url": "https://www.who.int/teams/integrated-health-services/clinical-services-and-systems/emergency-and-critical-care/emergency-care-toolkit",
        "scope": "Structured emergency assessment, referral and transfer tools for clinical teams.",
    },
    "who_dengue_primary_care": {
        "id": "who_dengue_primary_care",
        "title": "Dengue case management for primary health care and home-based care",
        "publisher": "WHO South-East Asia Regional Office",
        "year": 2025,
        "url": "https://www.who.int/southeastasia/publications/i/item/9789290221272",
        "scope": "Dengue recognition, referral and care pathways for health workers; not a replacement for local protocols.",
    },
    "who_arboviral_guideline": {
        "id": "who_arboviral_guideline",
        "title": "WHO guidelines for clinical management of arboviral diseases",
        "publisher": "World Health Organization",
        "year": 2025,
        "url": "https://www.who.int/publications/i/item/9789240111110",
        "scope": "Clinical management reference for dengue, chikungunya, Zika and yellow fever.",
    },
}

_DENGUE_SYMPTOMS = {"fever", "high_fever", "rash", "joint_pain", "headache"}


def retrieve_guidance_sources(
    *, symptoms: list[str], safety_flags: list[str], possible_condition: str = "",
) -> list[dict]:
    """Return only relevant source cards, ordered by acute-safety priority.

    The cards deliberately contain no patient-specific diagnosis, dose or
    treatment plan. A clinician must open and apply the primary source in the
    patient's local context.
    """
    source_ids: list[str] = []
    if safety_flags:
        source_ids.extend(["who_basic_emergency_care", "who_emergency_care_toolkit"])
    condition = possible_condition.lower()
    if "dengue" in condition or set(symptoms).intersection(_DENGUE_SYMPTOMS):
        source_ids.extend(["who_dengue_primary_care", "who_arboviral_guideline"])
    if not source_ids:
        source_ids.append("who_basic_emergency_care")

    seen: set[str] = set()
    return [
        {
            **_SOURCES[source_id],
            "retrieval_note": "Reference for clinician review; not patient-specific treatment advice.",
        }
        for source_id in source_ids
        if not (source_id in seen or seen.add(source_id))
    ]
