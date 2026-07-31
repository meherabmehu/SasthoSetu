# -*- coding: utf-8 -*-
"""Generate the multilingual symptom-triage training corpus.

Builds free-text symptom notes in Bangla, romanised Banglish, English and
code-switched forms, each labelled with a 5-level triage severity. Surface
forms, qualifiers, durations, greetings and trailers all come from the shared
lexicon (``backend/app/ai/lexicon.py``), so the corpus and the runtime
extractor can never drift apart.

Labelling is derived, not guessed: the severity of a note is the highest base
acuity among its symptoms, adjusted by intensity qualifier, duration and age,
and forced to level 5 whenever a red-flag combination is present. The label
therefore agrees with the deterministic safety layer by construction.

Deterministic: seed 42.

Output: data/triage/symptom_triage_dataset.csv
"""
from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.lexicon import (  # noqa: E402
    DURATIONS,
    GREETINGS,
    QUALIFIERS,
    SYMPTOMS,
    TRAILERS,
)
from app.ai.safety import check_red_flags  # noqa: E402

SEED = 42
TARGET_ROWS = 9000
OUT = ROOT / "data" / "triage"

LANGUAGES = ["bn", "bl", "en", "mixed"]
LANG_WEIGHTS = [0.42, 0.22, 0.16, 0.20]

# Symptom groups that co-occur clinically. Sampling from these instead of
# picking symptoms uniformly keeps the corpus medically plausible.
CO_OCCURRENCE = [
    ["fever", "body_ache", "headache"],
    ["fever", "cough", "sore_throat"],
    ["cough", "shortness_of_breath", "chest_pain"],
    ["chest_pain", "shortness_of_breath", "palpitations"],
    ["diarrhea", "vomiting", "abdominal_pain"],
    ["headache", "dizziness", "blurred_vision"],
    ["runny_nose", "sore_throat", "cough"],
    ["joint_pain", "body_ache", "fever"],
    ["heartburn", "abdominal_pain", "vomiting"],
    ["frequent_urination", "excessive_thirst", "fatigue"],
    ["skin_rash", "itching", "fever"],
    ["back_pain", "joint_pain"],
    ["anxiety", "palpitations", "insomnia"],
    ["weight_loss", "fatigue", "night_sweats"],
    ["swelling", "shortness_of_breath", "fatigue"],
]

# Presentations that must be labelled emergency. Kept explicit so the corpus
# always contains the red-flag combinations the safety layer screens for.
RED_FLAG_SETS = [
    ["chest_pain", "shortness_of_breath"],
    ["unconscious"],
    ["severe_bleeding"],
    ["high_fever", "stiff_neck"],
    ["facial_droop", "slurred_speech"],
    ["one_sided_numbness", "slurred_speech"],
    ["seizure"],
    ["blood_vomiting"],
    ["pregnancy_bleeding"],
    ["snake_bite"],
]

CONNECTORS = {
    "bn": [", ", " এবং ", " আর ", ", সাথে ", " ও "],
    "bl": [", ", " ar ", " and ", ", sathe "],
    "en": [", ", " and ", ", also ", " with "],
}


def _pick_lang(rng: random.Random) -> str:
    return rng.choices(LANGUAGES, weights=LANG_WEIGHTS, k=1)[0]


def _surface(rng: random.Random, symptom: str, lang: str) -> str:
    """A surface form for a symptom in the requested language."""
    entry = SYMPTOMS[symptom]
    if lang == "mixed":
        lang = rng.choice(["bn", "bl", "en"])
    forms = entry.get(lang) or entry.get("en") or [symptom]
    return rng.choice(forms)


def _qualifier(rng: random.Random, kind: str, lang: str) -> str:
    if lang == "mixed":
        lang = rng.choice(["bn", "bl", "en"])
    return rng.choice(QUALIFIERS[kind][lang])


def _duration(rng: random.Random, lang: str):
    bn, bl, en, days = rng.choice(DURATIONS)
    if lang == "mixed":
        lang = rng.choice(["bn", "bl", "en"])
    return {"bn": bn, "bl": bl, "en": en}[lang], days


def _label(symptoms, qualifier, duration_days, age) -> int:
    """Derive triage severity from clinical features."""
    flags = check_red_flags(symptoms, age)
    if flags:
        return 5

    level = max(SYMPTOMS[s]["level"] for s in symptoms)

    # Multiple concurrent moderate symptoms raise concern.
    if len(symptoms) >= 3 and level < 4:
        level += 1

    if qualifier == "severe" and level < 5:
        level += 1
    elif qualifier == "mild" and level > 1:
        level -= 1

    # Persistence matters: a complaint lasting weeks needs review.
    if duration_days is not None:
        if duration_days >= 14 and level < 4:
            level += 1
        elif duration_days == 0 and level > 1 and qualifier != "severe":
            level -= 1

    # Extremes of age lower the threshold for escalation.
    if age is not None and (age < 5 or age >= 65) and level < 5:
        level += 1

    return max(1, min(5, level))


def _compose(rng: random.Random, symptoms, lang, qualifier, duration_text, age):
    parts = []
    for index, symptom in enumerate(symptoms):
        text = _surface(rng, symptom, lang)
        if qualifier and index == 0:
            text = f"{_qualifier(rng, qualifier, lang)} {text}"
        parts.append(text)

    connector_lang = rng.choice(["bn", "bl", "en"]) if lang == "mixed" else lang
    connector = rng.choice(CONNECTORS[connector_lang])
    body = connector.join(parts)

    if duration_text:
        body = (
            f"{duration_text} {body}"
            if rng.random() < 0.5
            else f"{body} {duration_text}"
        )

    greet_lang = rng.choice(["bn", "bl", "en"]) if lang == "mixed" else lang
    greeting = rng.choice(GREETINGS[greet_lang])
    trailer = rng.choice(TRAILERS[greet_lang])

    age_text = ""
    if age is not None and rng.random() < 0.25:
        age_text = {
            "bn": f" বয়স {age}।",
            "bl": f" boyosh {age}.",
            "en": f" Age {age}.",
        }[greet_lang]

    return f"{greeting}{body}{age_text}{trailer}".strip()


def _sample_symptoms(rng: random.Random) -> list[str]:
    roll = rng.random()

    if roll < 0.12:
        group = list(rng.choice(RED_FLAG_SETS))
        if rng.random() < 0.3:
            extra = rng.choice(list(SYMPTOMS))
            if extra not in group:
                group.append(extra)
        return group

    if roll < 0.75:
        group = rng.choice(CO_OCCURRENCE)
        available = [s for s in group if s in SYMPTOMS]
        count = min(len(available), rng.randint(1, 3))
        return rng.sample(available, count)

    pool = list(SYMPTOMS)
    return rng.sample(pool, rng.randint(1, 2))


def main() -> None:
    rng = random.Random(SEED)
    OUT.mkdir(parents=True, exist_ok=True)

    rows = []
    seen = set()
    attempts = 0

    while len(rows) < TARGET_ROWS and attempts < TARGET_ROWS * 60:
        attempts += 1

        symptoms = _sample_symptoms(rng)
        if not symptoms:
            continue

        lang = _pick_lang(rng)
        qualifier = rng.choices(
            [None, "severe", "mild", "intermittent"],
            weights=[0.55, 0.2, 0.15, 0.10],
            k=1,
        )[0]

        duration_text, duration_days = (
            _duration(rng, lang) if rng.random() < 0.7 else (None, None)
        )
        age = rng.choice(
            [None, rng.randint(0, 4), rng.randint(5, 17),
             rng.randint(18, 45), rng.randint(46, 64), rng.randint(65, 90)]
        )

        text = _compose(rng, symptoms, lang, qualifier, duration_text, age)
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)

        qualifier_for_label = qualifier if qualifier in ("severe", "mild") else None
        label = _label(symptoms, qualifier_for_label, duration_days, age)

        rows.append(
            {
                "text": text,
                "language": lang,
                "symptoms": "|".join(symptoms),
                "duration_days": "" if duration_days is None else duration_days,
                "qualifier": qualifier or "",
                "age": "" if age is None else age,
                "triage_level": label,
            }
        )

    # Block-interleaved split keeps the class mix stable across the three sets.
    for index, row in enumerate(rows):
        position = index % 10
        row["split"] = "train" if position < 8 else ("val" if position == 8 else "test")

    path = OUT / "symptom_triage_dataset.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "text", "language", "symptoms", "duration_days",
                "qualifier", "age", "triage_level", "split",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    distribution = {}
    for row in rows:
        distribution[row["triage_level"]] = distribution.get(row["triage_level"], 0) + 1
    languages = {}
    for row in rows:
        languages[row["language"]] = languages.get(row["language"], 0) + 1

    print(f"rows={len(rows)} -> {path}")
    print("level distribution:", dict(sorted(distribution.items())))
    print("language distribution:", dict(sorted(languages.items())))


if __name__ == "__main__":
    main()
