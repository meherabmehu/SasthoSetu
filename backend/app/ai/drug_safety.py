# -*- coding: utf-8 -*-
"""BanglaMed-AI drug-safety checker.

Normalises Bangladeshi brand names (Napa -> paracetamol, Seclo -> omeprazole)
via ``data/drugs/bd_brand_aliases.csv``, then checks every drug pair against
the curated interaction knowledge base ``data/drugs/drug_interactions.csv``.

Used by POST /v1/prescriptions/verify (flagged_interactions field) and by the
doctor-side AI assist. The knowledge base is a curated demo subset, not an
exhaustive pharmacology database — stated plainly in the model card.
"""
from __future__ import annotations

import csv
import os
from functools import lru_cache
from itertools import combinations
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATA_DIR = Path(os.environ.get("SASTHOSETU_DATA_DIR", _REPO_ROOT / "data"))

_SEVERITY_RANK = {"major": 3, "moderate": 2, "minor": 1}


@lru_cache(maxsize=1)
def _aliases() -> dict[str, str]:
    path = _DATA_DIR / "drugs" / "bd_brand_aliases.csv"
    table: dict[str, str] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            table[row["brand"].strip().lower()] = row["generic"].strip().lower()
    return table


@lru_cache(maxsize=1)
def _interactions() -> dict[frozenset, dict]:
    path = _DATA_DIR / "drugs" / "drug_interactions.csv"
    table: dict[frozenset, dict] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = frozenset({row["drug_a"].strip().lower(),
                             row["drug_b"].strip().lower()})
            table[key] = row
    return table


def normalize_drug(name: str) -> str:
    """Lower-case, strip dosage suffixes, resolve BD brand -> generic."""
    n = (name or "").strip().lower()
    for token in (" tablet", " tab", " capsule", " cap", " syrup", " mg", " ml"):
        n = n.replace(token, "")
    n = n.split("(")[0].strip()
    # drop trailing strength like "napa 500" -> "napa"
    parts = [p for p in n.split() if not p.replace(".", "").isdigit()]
    n = " ".join(parts)
    return _aliases().get(n, n)


def check_interactions(drugs: list[str]) -> dict:
    """Check all pairs among the given drug names (brands or generics)."""
    normalized = [normalize_drug(d) for d in drugs if d and d.strip()]
    seen_pairs, findings = set(), []
    for a, b in combinations(normalized, 2):
        key = frozenset({a, b})
        if len(key) < 2 or key in seen_pairs:
            continue
        seen_pairs.add(key)
        hit = _interactions().get(key)
        if hit:
            findings.append({
                "drug_a": hit["drug_a"], "drug_b": hit["drug_b"],
                "severity": hit["severity"],
                "effect": hit["effect_en"],
                "advice": {"en": hit["advice_en"], "bn": hit["advice_bn"]},
            })
    findings.sort(key=lambda f: _SEVERITY_RANK.get(f["severity"], 0),
                  reverse=True)
    return {
        "input_drugs": drugs,
        "normalized_drugs": normalized,
        "flagged_interactions": findings,
        "highest_severity": findings[0]["severity"] if findings else None,
        "knowledge_base": "curated-demo-v1 (45 pairs, BD brand-aware)",
    }


if __name__ == "__main__":
    import json
    demo = ["Napa 500", "Seclo 20", "Clopid 75", "Ecosprin 75"]
    print(json.dumps(check_interactions(demo), indent=2, ensure_ascii=False))
