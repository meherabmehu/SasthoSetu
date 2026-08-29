# -*- coding: utf-8 -*-
"""Combine the generated Bangla corpus with real English ED visits.

The project serves patients in Bangla and English, and the two languages are in
very different positions. For English there is real data: the US CDC's national
ED survey records a nurse-assigned triage level against the patient's reason for
visiting, with vital signs. For Bangla no equivalent exists, so those rows stay
generated until a clinical partner supplies real ones.

Two things the real rows fix:

**The severity prior.** The generated corpus is close to uniform across the five
levels. Real triage is nothing like that — over half of arrivals sit at level 3
and the extremes are rare. A model trained on a uniform corpus carries a prior
no emergency department has ever seen.

**English phrasing.** The generated English is assembled from lexicon surface
forms. The survey's reason-for-visit wording is what clinicians actually record.

Real rows are converted to notes rather than used as bare codes, so they enter
the same text pipeline as everything else. The conversion joins the recorded
reasons with the patient's age and temperature when present — no invented
detail, only what the survey holds.

    python ml/build_triage_corpus.py

Output: data/triage/symptom_triage_dataset.csv, with a ``source`` column
distinguishing generated rows from real ones.
"""
from __future__ import annotations

import csv
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

GENERATED = ROOT / "data" / "triage" / "symptom_triage_dataset.csv"
REAL = ROOT / "data" / "real" / "nhamcs_ed_triage.csv"
BANGLA_REAL = ROOT / "data" / "real" / "bangla_from_nhamcs.csv"
OUT = GENERATED

SEED = 42

# The survey records up to three reasons per visit. Joining them the way a
# patient would speak keeps the note in the same register as the rest of the
# corpus rather than reading like a form.
JOINERS = [", ", ", also ", " and "]

PREFIXES = [
    "",
    "",
    "",
    "I have ",
    "Patient reports ",
    "Complaining of ",
    "Came in with ",
]


def _clean(reason: str) -> str:
    """Turn survey wording into something a person would say.

    The classification uses abbreviations that belong in a codebook, not in a
    sentence, and capitalises the first word of every entry.
    """
    text = reason.strip()
    for suffix in (", NOS", ", NEC", " NOS", " NEC"):
        text = text.replace(suffix, "")
    text = text.replace(" - ", " ")
    # Entries such as "Abdominal pain, cramps, spasms," leave a trailing comma
    # once the NOS marker is stripped, and doubled separators read as a typo
    # rather than as speech.
    text = re.sub(r",\s*,+", ",", text)
    text = " ".join(text.split()).strip(" ,;")
    if text and text[0].isupper() and not text.isupper():
        # Only lowercase an ordinary sentence start, never an acronym.
        words = text.split(" ", 1)
        if len(words[0]) > 1 and words[0][1:].islower():
            text = text[0].lower() + text[1:]
    return text


def _note(rng: random.Random, reasons: list[str], age, temperature) -> str:
    parts = [_clean(r) for r in reasons if r.strip()]
    if not parts:
        return ""

    parts = [p for p in parts if p]
    if not parts:
        return ""

    text = parts[0]
    for extra in parts[1:]:
        text += rng.choice(JOINERS) + extra

    text = rng.choice(PREFIXES) + text

    # Age and temperature are separate columns in the survey. Mentioning them
    # in the note some of the time teaches the model to read them from text as
    # well as from the structured fields, which is how patients supply them.
    if age and rng.random() < 0.30:
        try:
            years = int(float(age))
            if 0 < years < 120:
                text += f", age {years}"
        except ValueError:
            pass

    if temperature and rng.random() < 0.25:
        try:
            celsius = float(temperature)
            if 30 <= celsius <= 45:
                text += f", temperature {celsius}"
        except ValueError:
            pass

    return text


def _load_real(rng: random.Random) -> list[dict]:
    if not REAL.exists():
        print(f"  {REAL.relative_to(ROOT)} is missing — "
              "run ml/fetch_real_data.py first")
        return []

    rows = []
    with REAL.open(encoding="utf-8") as fh:
        for record in csv.DictReader(fh):
            reasons = [
                record.get("reason_1", ""),
                record.get("reason_2", ""),
                record.get("reason_3", ""),
            ]
            note = _note(rng, reasons, record.get("age_years"),
                         record.get("temperature_c"))
            if len(note) < 3:
                continue

            level = record.get("severity_level", "").strip()
            if level not in {"1", "2", "3", "4", "5"}:
                continue

            age = ""
            try:
                years = int(float(record.get("age_years") or 0))
                if 0 < years < 120:
                    age = years
            except ValueError:
                pass

            rows.append({
                "text": note,
                "language": "en",
                "symptoms": "",
                "duration_days": "",
                "qualifier": "",
                "age": age,
                "triage_level": int(level),
                "split": "",
                "source": "nhamcs",
            })
    return rows


def _load_bangla_real() -> list[dict]:
    """Bangla and Banglish notes derived from the real ED presentations.

    Built by ml/build_bangla_from_real.py, which routes each recorded English
    complaint through the symptom lexicon so the Bangla reads the way a patient
    writes it. Severity is on our scale, derived by the same rules as the rest
    of the corpus.
    """

    if not BANGLA_REAL.exists():
        return []

    rows = []
    with BANGLA_REAL.open(encoding="utf-8") as fh:
        for record in csv.DictReader(fh):
            level = record.get("triage_level", "").strip()
            if level not in {"1", "2", "3", "4", "5"}:
                continue
            rows.append({
                "text": record["text"],
                "language": record["language"],
                "symptoms": record.get("symptoms", ""),
                "duration_days": "",
                "qualifier": "",
                "age": record.get("age", ""),
                "triage_level": int(level),
                "split": "",
                "source": "nhamcs_bangla",
            })
    return rows


def main() -> None:
    rng = random.Random(SEED)

    print("=== Generated corpus")
    subprocess.run(
        [sys.executable, str(ROOT / "ml" / "generate_triage_dataset.py")],
        check=True,
    )

    with GENERATED.open(encoding="utf-8") as fh:
        generated = list(csv.DictReader(fh))
    for row in generated:
        row["source"] = "generated"
    print(f"  generated rows: {len(generated):,}")

    print("\n=== Real emergency department visits")
    # The English rows are deliberately NOT trained on. They carry the survey's
    # own urgency scale, which answers "how fast must this person be seen now
    # that they are in an emergency department" — not "what should someone at
    # home do". Training on both scales at once cost 15 points of macro-F1 and
    # collapsed level-4 recall. They are still used, as vocabulary, by
    # ml/extend_lexicon_from_real.py.
    english = _load_real(rng)
    print(f"  real English (vocabulary only, not trained on): {len(english):,}")

    real = _load_bangla_real()
    print(f"  real Bangla/Banglish (trained on)             : {len(real):,}")

    if not real:
        print("\nNo real rows available; leaving the generated corpus as is.")
        return

    # The real rows carry their own split so a model is never validated on a
    # generated row that happens to resemble a real one it trained on.
    rng.shuffle(real)
    for index, row in enumerate(real):
        position = index % 10
        row["split"] = (
            "train" if position < 8 else ("val" if position == 8 else "test")
        )

    combined = generated + real
    rng.shuffle(combined)

    fieldnames = [
        "text", "language", "symptoms", "duration_days",
        "qualifier", "age", "triage_level", "split", "source",
    ]
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in combined:
            writer.writerow({key: row.get(key, "") for key in fieldnames})

    print(f"\nwrote {OUT.relative_to(ROOT)}: {len(combined):,} rows")

    from collections import Counter
    by_source = Counter(row["source"] for row in combined)
    by_level = Counter(str(row["triage_level"]) for row in combined)
    real_level = Counter(str(row["triage_level"]) for row in real)

    print("\n  source        rows")
    for name, count in sorted(by_source.items()):
        print(f"  {name:12} {count:6,}")

    print("\n  level   corpus     real only")
    for level in "12345":
        share = 100 * by_level[level] / len(combined)
        real_share = (
            100 * real_level[level] / len(real) if real else 0
        )
        print(f"  {level}     {by_level[level]:6,} ({share:4.1f}%)"
              f"   {real_level[level]:5,} ({real_share:4.1f}%)")


if __name__ == "__main__":
    main()
