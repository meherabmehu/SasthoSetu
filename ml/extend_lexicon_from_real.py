# -*- coding: utf-8 -*-
"""Report which real complaint wordings the symptom lexicon does not recognise.

The lexicon was written from clinical knowledge and from how Bangladeshi
patients speak. What it was never checked against is the vocabulary clinicians
actually record, because until now there was no real corpus to check against.

The US ED survey supplies 508 distinct complaint phrasings drawn from real
visits. Running the extractor over them shows exactly where the lexicon is
blind — "dyspnea", "syncope", "nasal congestion" and so on are ordinary
clinical words that a patient or a nurse may well type.

This script only reports. Adding a surface form to the lexicon is a clinical
decision about what a phrase means, so it is made deliberately in
``lexicon_symptoms.py`` rather than generated.

    python ml/extend_lexicon_from_real.py
    python ml/extend_lexicon_from_real.py --top 50
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.extraction import extract  # noqa: E402

REAL = ROOT / "data" / "real" / "nhamcs_ed_triage.csv"

# Entries that describe an administrative event, a body region with no
# complaint attached, or a diagnosis rather than a symptom. These are not
# lexicon gaps and listing them as such would be noise.
NOT_SYMPTOMS = (
    "counseling", "examination", "medication", "postoperative",
    "insufficient information", "progress visit", "wound check",
    "no complaint", "illegible", "unable to speak", "refused care",
    "screening", "test result", "immunization", "referral",
    "administrative", "follow-up", "follow up", "prescription",
)


def _is_symptom(text: str) -> bool:
    lowered = text.lower()
    return not any(marker in lowered for marker in NOT_SYMPTOMS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=80,
                        help="how many unrecognised phrasings to list")
    args = parser.parse_args()

    if not REAL.exists():
        print(f"{REAL.relative_to(ROOT)} is missing — "
              "run ml/fetch_real_data.py first")
        sys.exit(1)

    counts: Counter[str] = Counter()
    with REAL.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            for key in ("reason_1", "reason_2", "reason_3"):
                value = row[key].strip()
                if value:
                    counts[value] += 1

    recognised = []
    missing = []
    for phrase, count in counts.most_common():
        if not _is_symptom(phrase):
            continue
        if extract(phrase).symptoms:
            recognised.append((phrase, count))
        else:
            missing.append((phrase, count))

    total = len(recognised) + len(missing)
    covered = sum(c for _, c in recognised)
    uncovered = sum(c for _, c in missing)

    print(f"distinct clinical phrasings : {total}")
    print(f"  recognised                : {len(recognised)} "
          f"({covered:,} mentions)")
    print(f"  not recognised            : {len(missing)} "
          f"({uncovered:,} mentions)")
    print(f"  mention coverage          : "
          f"{100 * covered / (covered + uncovered):.1f}%")

    print(f"\nMost frequent unrecognised phrasings (top {args.top}):")
    for phrase, count in missing[:args.top]:
        print(f"  {count:5}  {phrase}")


if __name__ == "__main__":
    main()
