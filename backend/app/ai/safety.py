# -*- coding: utf-8 -*-
"""BanglaMed-AI hard-coded safety rules.

Per the Enhanced Platform document (section 4.2, "Critical safety rule"):
certain symptom combinations auto-escalate to Emergency (level 5) REGARDLESS
of the ML classifier output. The AI never downgrades these. This module is
deliberately simple, auditable, and unit-testable — clinical safety logic
must not hide inside model weights.
"""
from __future__ import annotations

from typing import Optional

# Each rule: (flag_name, human description en/bn, predicate)
# predicate(symptoms: set, age: Optional[int]) -> bool


def _has(symptoms: set, *names: str) -> bool:
    return all(n in symptoms for n in names)


def _any(symptoms: set, *names: str) -> bool:
    return any(n in symptoms for n in names)


RED_FLAG_RULES = [
    {
        "flag": "possible_cardiac_event",
        "en": "Chest pain together with breathing difficulty — possible cardiac event",
        "bn": "বুকে ব্যথার সাথে শ্বাসকষ্ট — সম্ভাব্য হার্টের জরুরি অবস্থা",
        "test": lambda s, a: _has(s, "chest_pain", "shortness_of_breath"),
    },
    {
        "flag": "altered_consciousness",
        "en": "Loss of consciousness / unresponsiveness",
        "bn": "অজ্ঞান বা অচেতন অবস্থা",
        "test": lambda s, a: _any(s, "unconscious"),
    },
    {
        "flag": "severe_bleeding",
        "en": "Severe or uncontrolled bleeding",
        "bn": "তীব্র বা অনিয়ন্ত্রিত রক্তক্ষরণ",
        "test": lambda s, a: _any(s, "severe_bleeding"),
    },
    {
        "flag": "possible_meningitis",
        "en": "Fever with stiff neck — possible meningitis",
        "bn": "জ্বরের সাথে ঘাড় শক্ত — সম্ভাব্য মেনিনজাইটিস",
        "test": lambda s, a: _any(s, "fever", "high_fever") and "stiff_neck" in s,
    },
    {
        "flag": "possible_stroke",
        "en": "Facial droop / slurred speech / one-sided weakness — possible stroke (FAST)",
        "bn": "মুখ বেঁকে যাওয়া / কথা জড়ানো / এক পাশ অবশ — সম্ভাব্য স্ট্রোক",
        "test": lambda s, a: _any(s, "facial_droop", "slurred_speech", "one_sided_numbness"),
    },
    {
        "flag": "seizure",
        "en": "Active seizure / convulsions",
        "bn": "খিঁচুনি",
        "test": lambda s, a: _any(s, "seizure"),
    },
    {
        "flag": "gi_bleed",
        "en": "Vomiting blood — possible GI bleed",
        "bn": "রক্ত বমি — সম্ভাব্য অভ্যন্তরীণ রক্তক্ষরণ",
        "test": lambda s, a: _any(s, "blood_vomiting"),
    },
    {
        "flag": "obstetric_emergency",
        "en": "Bleeding during pregnancy — obstetric emergency",
        "bn": "গর্ভাবস্থায় রক্তপাত — প্রসূতি জরুরি অবস্থা",
        "test": lambda s, a: _any(s, "pregnancy_bleeding"),
    },
    {
        "flag": "envenomation",
        "en": "Snake bite — anti-venom time-critical",
        "bn": "সাপে কামড় — দ্রুত অ্যান্টিভেনম প্রয়োজন",
        "test": lambda s, a: _any(s, "snake_bite"),
    },
    {
        "flag": "infant_high_fever",
        "en": "High fever in an infant under 1 year",
        "bn": "১ বছরের কম বয়সী শিশুর তীব্র জ্বর",
        "test": lambda s, a: a is not None and a < 1 and _any(s, "high_fever", "fever"),
    },
]


def check_red_flags(symptoms: list[str] | set, age: Optional[int] = None) -> list[dict]:
    """Return the list of triggered red-flag dicts (may be empty)."""
    sset = set(symptoms)
    return [
        {"flag": r["flag"], "en": r["en"], "bn": r["bn"]}
        for r in RED_FLAG_RULES
        if r["test"](sset, age)
    ]


def apply_safety_override(predicted_level: int, flags: list[dict]) -> int:
    """Escalate to Emergency whenever any red flag fired."""
    return 5 if flags else predicted_level
