# -*- coding: utf-8 -*-
"""Turn real English ED complaints into Bangla training notes.

The US ED survey gives 9,446 real visits, each with a clinician-assigned
urgency and the complaints that were recorded. The text is English clinical
shorthand — "Abdominal pain, cramps, spasms, NOS" — which is not how a
Bangladeshi patient writes.

Machine-translating that shorthand produces stilted Bangla nobody uses. So the
translation goes through the symptom lexicon instead:

    "Chest pain, Soreness"  ->  chest_pain  ->  "বুকে ব্যথা"

Every Bangla surface form already in the lexicon was written as a patient would
say it, so routing through the canonical id yields natural Bangla rather than a
literal rendering of a codebook entry. The same route gives romanised Banglish
for free.

**The urgency label is not carried over.** The survey asks how quickly someone
already inside an emergency department must be seen; SasthoSetu asks what a
person at home should do, which includes "nothing yet". Mixing the two scales
was tried and cost 32 points of macro-F1. What is carried over is the
*presentation*: which symptoms really co-occur, at what ages, with what vitals.
The severity is then derived by the same rules that label the rest of the
corpus, so the whole training set stays on one scale.

    python ml/build_bangla_from_real.py

Output: data/real/bangla_from_nhamcs.csv
"""
from __future__ import annotations

import csv
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.extraction import extract  # noqa: E402
from app.ai.lexicon import (  # noqa: E402
    GREETINGS,
    SYMPTOMS,
    TRAILERS,
)
from app.ai.safety import check_red_flags  # noqa: E402

SEED = 42
REAL = ROOT / "data" / "real" / "nhamcs_ed_triage.csv"
OUT = ROOT / "data" / "real" / "bangla_from_nhamcs.csv"

# Written the way a patient joins complaints, not the way a form lists them.
JOINERS_BN = [", ", " আর ", " এবং ", ", সাথে "]
JOINERS_BL = [", ", " ar ", " ebong ", ", sathe "]

AGE_BN = "বয়স {age} বছর"
AGE_BL = "boyosh {age} bochor"
TEMP_BN = "জ্বর {temp} ডিগ্রি"
TEMP_BL = "jor {temp} degree"


def _surface(rng: random.Random, canonical: str, lang: str) -> str:
    """A natural surface form for this symptom in the requested language."""
    entry = SYMPTOMS.get(canonical)
    if not entry:
        return ""
    forms = entry.get(lang) or entry.get("en") or []
    return rng.choice(list(forms)) if forms else ""


def _label(symptoms: list[str], age: int | None) -> int:
    """Severity on our own scale, by the same rules as the generated corpus.

    Deriving the label rather than importing the survey's keeps the whole
    training set answering one question, and keeps it consistent with the
    deterministic safety layer at serving time.
    """
    if not symptoms:
        return 1

    if check_red_flags(symptoms, age):
        return 5

    level = max(SYMPTOMS[s]["level"] for s in symptoms if s in SYMPTOMS)

    if len(symptoms) >= 3 and level < 4:
        level += 1
    if age is not None and (age < 5 or age >= 65) and level < 5:
        level += 1

    return max(1, min(5, level))


def main() -> None:
    if not REAL.exists():
        print(f"{REAL.relative_to(ROOT)} is missing — "
              "run ml/fetch_real_data.py first")
        raise SystemExit(1)

    rng = random.Random(SEED)

    with REAL.open(encoding="utf-8") as fh:
        visits = list(csv.DictReader(fh))

    rows = []
    untranslatable = Counter()

    for visit in visits:
        # Resolve the recorded complaints to canonical symptoms. Anything the
        # lexicon does not know is dropped rather than guessed at.
        canonical: list[str] = []
        for key in ("reason_1", "reason_2", "reason_3"):
            phrase = visit[key].strip()
            if not phrase:
                continue
            found = extract(phrase).symptoms
            if found:
                canonical.extend(found)
            else:
                untranslatable[phrase] += 1

        canonical = list(dict.fromkeys(canonical))
        if not canonical:
            continue

        try:
            age = int(float(visit["age_years"])) if visit["age_years"] else None
        except ValueError:
            age = None
        if age is not None and not (0 < age < 120):
            age = None

        temperature = visit.get("temperature_c", "").strip()

        for lang in ("bn", "bl"):
            parts = [_surface(rng, c, lang) for c in canonical]
            parts = [p for p in parts if p]
            if not parts:
                continue

            joiners = JOINERS_BN if lang == "bn" else JOINERS_BL
            text = parts[0]
            for extra in parts[1:]:
                text += rng.choice(joiners) + extra

            if age and rng.random() < 0.35:
                template = AGE_BN if lang == "bn" else AGE_BL
                text += ", " + template.format(age=age)

            if temperature and rng.random() < 0.20:
                try:
                    celsius = float(temperature)
                    if 37.5 <= celsius <= 45:
                        template = TEMP_BN if lang == "bn" else TEMP_BL
                        text += ", " + template.format(temp=celsius)
                except ValueError:
                    pass

            if rng.random() < 0.25:
                greeting = rng.choice(GREETINGS.get(lang, GREETINGS["bn"]))
                text = f"{greeting} {text}"
            if rng.random() < 0.20:
                trailer = rng.choice(TRAILERS.get(lang, TRAILERS["bn"]))
                text = f"{text} {trailer}"

            rows.append({
                "text": text,
                "language": lang,
                "symptoms": "|".join(canonical),
                "age": age or "",
                "triage_level": _label(canonical, age),
                "source": "nhamcs_bangla",
            })

    rng.shuffle(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["text", "language", "symptoms", "age",
                        "triage_level", "source"],
        )
        writer.writeheader()
        writer.writerows(rows)

    by_lang = Counter(r["language"] for r in rows)
    by_level = Counter(str(r["triage_level"]) for r in rows)

    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows):,} notes "
          f"from {len(visits):,} real visits")
    print("  by language:", dict(by_lang))
    print("  by level   :", {k: by_level[k] for k in sorted(by_level)})
    print(f"  complaints the lexicon could not translate: "
          f"{len(untranslatable)} distinct")
    for phrase, count in untranslatable.most_common(5):
        print(f"    {count:5}  {phrase[:64]}")


if __name__ == "__main__":
    main()
