"""Create a privacy-preserving external audit for the Bangla severity corpus.

This public corpus has four manually assigned categories, not SasthoSetu's
five-level clinician-labelled taxonomy.  It is therefore never fed into model
training.  The output contains aggregate results and text hashes only.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "real" / "_cache" / "bangla_severity_v1.zip"
REPORT = ROOT / "backend" / "app" / "ai" / "artifacts" / "bangla_severity_external_audit.json"


def _records():
    with zipfile.ZipFile(CACHE) as archive:
        member = next(name for name in archive.namelist()
                      if name.endswith("Bangla-Healthcare_Dataset.csv"))
        # The source mixes UTF-8 Bangla text with a few Windows punctuation
        # bytes. Replacement preserves the Bangla text without failing closed.
        text = io.TextIOWrapper(archive.open(member), encoding="utf-8", errors="replace")
        yield from csv.DictReader(text)


def audit() -> dict:
    if not CACHE.exists():
        raise FileNotFoundError(f"Missing source archive: {CACHE}")
    counts: Counter[str] = Counter()
    replacement_heavy_rows = 0
    total_question_marks = 0
    total_characters = 0
    for row in _records():
        category = row["Categories"].strip()
        text = row["Text"]
        counts[category] += 1
        question_ratio = text.count("?") / max(1, len(text))
        replacement_heavy_rows += question_ratio > 0.5
        total_question_marks += text.count("?")
        total_characters += len(text)
    report = {
        "source": "https://data.mendeley.com/datasets/37z8kgx79m/1",
        "licence": "CC BY 4.0",
        "rows": sum(counts.values()),
        "category_counts": dict(sorted(counts.items())),
        "text_integrity": {
            "question_mark_ratio": round(total_question_marks / max(1, total_characters), 4),
            "rows_over_50_percent_question_marks": replacement_heavy_rows,
            "usable_for_text_training_or_evaluation": False,
        },
        "method": "Metadata and text-integrity audit only; no source text is committed.",
        "not_a_training_set": True,
        "not_clinician_labelled": True,
        "exclusion_reason": "The released CSV substitutes most Bangla text with question marks, and its four source categories cannot safely map to the product's five clinical urgency levels.",
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
