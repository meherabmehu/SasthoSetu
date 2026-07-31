# -*- coding: utf-8 -*-
"""BanglaMed-AI entity extraction.

Rule-based extraction of clinical entities from free-text Bangla / Banglish /
English / code-switched symptom notes. Designed to be dependency-free (stdlib
only) so it runs inside the FastAPI serving path with zero latency overhead.

Extracted entities:
    * canonical symptoms (lexicon surface-form matching, longest-match-first)
    * duration in days (Bangla numerals, Bangla number-words, English, Banglish)
    * severity qualifier (severe / mild / intermittent)
    * patient age if stated
    * simple negation ("জ্বর নেই" removes fever)

Known limitations (documented honestly): negation handling is window-based and
approximate; no coreference; misspellings outside lexicon variants are handled
downstream by the char-ngram classifier, not here.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from .lexicon import BN_DIGITS, BN_NUM_WORDS, QUALIFIERS, SYMPTOMS


# --------------------------------------------------------------------------
# Normalisation
# --------------------------------------------------------------------------
_PUNCT_RE = re.compile(r"[,;:!?\u0964\u2018\u2019\"'()\[\]{}]")  # \u0964 = দাঁড়ি


def normalize(text: str) -> str:
    """NFC-normalise, translate Bangla digits, lowercase latin, squeeze spaces."""
    text = unicodedata.normalize("NFC", text or "")
    text = "".join(BN_DIGITS.get(ch, ch) for ch in text)
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# --------------------------------------------------------------------------
# Surface-form index (built once at import)
# --------------------------------------------------------------------------
def _build_surface_index() -> list[tuple[str, str, int]]:
    pairs: list[tuple[str, str, int]] = []
    for canonical, entry in SYMPTOMS.items():
        level = entry.get("level", 0)
        for lang in ("bn", "bl", "en"):
            for form in entry[lang]:
                pairs.append((normalize(form), canonical, level))
    # longest first so "তীব্র জ্বর" wins over "জ্বর"
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


_SURFACE_INDEX = _build_surface_index()

# Bangla negation particles follow the symptom ("জ্বর নেই"); English negation
# precedes it ("no fever"). They are matched in different windows accordingly.
_NEG_AFTER = ["নেই", "নাই", "হয়নি", "হয় নি", "nei", "nai"]
_NEG_BEFORE = ["no", "not", "without", "denies", "na"]

# Phrases where a negation token intensifies rather than negates the symptom.
# "bleeding will not stop" is more severe, not absent - treating it as a
# negation would silently drop a red flag.
_NEG_EXEMPT = [
    "not stop", "not stopping", "wont stop", "won't stop", "not stopped",
    "cannot stop", "can't stop", "cant stop", "not controlled",
    "not responding", "not breathing", "cannot breathe", "can't breathe",
    "cant breathe", "not moving", "not waking", "not conscious",
    "bondho hocche na", "bondho hoy na", "থামছে না", "বন্ধ হচ্ছে না",
]

_DUR_UNIT_DAYS = {
    "দিন": 1, "din": 1, "day": 1, "days": 1,
    "সপ্তাহ": 7, "shoptaho": 7, "week": 7, "weeks": 7,
    "মাস": 30, "mash": 30, "month": 30, "months": 30,
    "ঘণ্টা": 0, "ghonta": 0, "hour": 0, "hours": 0,  # < 1 day -> 0
    "বছর": 365, "bochor": 365, "year": 365, "years": 365,
}

_EN_NUMS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4,
            "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_ALL_NUM_WORDS = {**BN_NUM_WORDS, **_EN_NUMS}

_DUR_RE = re.compile(
    r"(\d+|" + "|".join(map(re.escape, _ALL_NUM_WORDS)) + r")\s*"
    r"(দিন|সপ্তাহ|মাস|ঘণ্টা|বছর|din|shoptaho|mash|ghonta|bochor|days?|weeks?|months?|hours?|years?)"
)

_AGE_RE = re.compile(
    r"(?:বয়স|age|boyosh)\s*(\d+)|(\d+)\s*(?:বছর|bochor|years?\s*old|yrs?\b|yo\b)"
)


@dataclass
class ExtractionResult:
    symptoms: list[str] = field(default_factory=list)
    negated_symptoms: list[str] = field(default_factory=list)
    duration_days: Optional[int] = None
    qualifier: Optional[str] = None            # severe | mild | intermittent
    age: Optional[int] = None
    normalized_text: str = ""

    def to_dict(self) -> dict:
        return {
            "symptoms": self.symptoms,
            "negated_symptoms": self.negated_symptoms,
            "duration_days": self.duration_days,
            "qualifier": self.qualifier,
            "age": self.age,
        }


def _is_negated(norm: str, start: int, end: int) -> bool:
    """Decide whether the symptom span at [start:end) is negated."""
    after = norm[end: end + 18]
    before = norm[max(0, start - 22): start]

    context = (before + " " + norm[start:end] + " " + after).strip()
    if any(phrase in context for phrase in _NEG_EXEMPT):
        return False

    if any(re.search(r"(^|\s)" + re.escape(m) + r"(\s|$)", after) for m in _NEG_AFTER):
        return True

    before_tokens = before.split()
    if before_tokens and before_tokens[-3:]:
        if any(tok in _NEG_BEFORE for tok in before_tokens[-3:]):
            return True
    return False


def _find_symptoms(norm: str) -> tuple[list[str], list[str]]:
    """Match symptom surface forms, resolving overlaps in favour of acuity.

    Longer surface forms are tried first, but when two candidate matches
    overlap the higher-acuity symptom wins. This prevents a generic low-level
    match (for example "বমি") from consuming the span of a red-flag symptom
    (for example "রক্ত বমি").
    """
    spans: list[tuple[int, int, str, int]] = []  # start, end, canonical, level
    for surface, canonical, level in _SURFACE_INDEX:
        if not surface:
            continue
        start = norm.find(surface)
        while start != -1:
            spans.append((start, start + len(surface), canonical, level))
            start = norm.find(surface, start + 1)

    # Prefer higher acuity, then longer match, then earlier position.
    spans.sort(key=lambda s: (-s[3], -(s[1] - s[0]), s[0]))

    taken: list[tuple[int, int]] = []
    found: list[str] = []
    negated: list[str] = []
    for start, end, canonical, _level in spans:
        if any(start < t_end and end > t_start for t_start, t_end in taken):
            continue
        taken.append((start, end))
        target = negated if _is_negated(norm, start, end) else found
        if canonical not in target:
            target.append(canonical)

    found = [s for s in found if s not in negated]
    return found, negated


def _find_duration(norm: str) -> Optional[int]:
    best: Optional[int] = None
    for m in _DUR_RE.finditer(norm):
        qty_raw, unit = m.group(1), m.group(2)
        qty = int(qty_raw) if qty_raw.isdigit() else _ALL_NUM_WORDS.get(qty_raw, 1)
        days = qty * _DUR_UNIT_DAYS.get(unit, 1) if _DUR_UNIT_DAYS.get(unit, 1) else 0
        best = days if best is None else max(best, days)
    if best is None:
        if "আজ" in norm or "aj " in norm or "today" in norm or "morning" in norm:
            best = 0
        elif "গতকাল" in norm or "gotokal" in norm or "yesterday" in norm:
            best = 1
    return best


def _find_qualifier(norm: str) -> Optional[str]:
    for kind in ("severe", "mild", "intermittent"):
        for lang in ("bn", "bl", "en"):
            for form in QUALIFIERS[kind][lang]:
                if normalize(form) in norm:
                    return kind
    return None


def _find_age(norm: str) -> Optional[int]:
    m = _AGE_RE.search(norm)
    if not m:
        return None
    val = m.group(1) or m.group(2)
    try:
        age = int(val)
        return age if 0 < age < 120 else None
    except (TypeError, ValueError):
        return None


def extract(text: str) -> ExtractionResult:
    """Extract all clinical entities from a raw symptom note."""
    norm = normalize(text)
    symptoms, negated = _find_symptoms(norm)
    return ExtractionResult(
        symptoms=symptoms,
        negated_symptoms=negated,
        duration_days=_find_duration(norm),
        qualifier=_find_qualifier(norm),
        age=_find_age(norm),
        normalized_text=norm,
    )


if __name__ == "__main__":  # quick smoke test
    samples = [
        "বুকে ব্যথা, শ্বাস নিতে কষ্ট, দুই দিন ধরে জ্বর",
        "amar 3 din dhore matha betha r bomi hocche",
        "High fever with শরীর ব্যথা since yesterday, বয়স ৪৫",
        "জ্বর নেই কিন্তু কাশি আছে এক সপ্তাহ ধরে",
    ]
    for s in samples:
        print(s, "->", extract(s).to_dict())
