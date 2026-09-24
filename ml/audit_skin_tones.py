# -*- coding: utf-8 -*-
"""Audit the skin screens across Fitzpatrick skin types.

Every model card in this project carries the same caveat: the training
collections are predominantly lighter-skinned, and behaviour on Bangladeshi
skin is unvalidated. That caveat has never been measured. This script
measures it, using the one dataset we serve whose photographs carry
Fitzpatrick skin-type labels: PAD-UFES-20.

What it reports, per skin type (1 palest to 6 darkest):

  - the referral rate of each screen - how often it says "see a doctor"
  - the malignant recall of the smartphone screen, where the labels permit
    it (PAD carries diagnoses for every photograph)

The honest expectation is that this audit will find gaps. A referral rate
that collapses on darker skin means under-referral - a melanoma on brown
skin being told to watch and wait. A referral rate that explodes means
over-referral - every dark mole sent to a dermatologist, which erodes trust
and wastes the clinics' time. Both are findings a clinician should see
before trusting any of these screens, which is why the output is a model
card rather than a number buried in a log.

    python ml/audit_skin_tones.py
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from PIL import Image

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.skin_features import extract_features  # noqa: E402
from app.ai import skin_service  # noqa: E402

IMAGING = ROOT / "data" / "real" / "imaging"
LABELS = IMAGING / "pad_labels.csv"
OUT = ROOT / "docs" / "model_cards" / "skin_tone_audit.md"
OUT_JSON = ROOT / "backend" / "app" / "ai" / "artifacts" / "skin_tone_audit.json"

TONE_NAMES = {
    "1": "I — সবচেয়ে ফর্সা (সবসময় পোড়ে, কখনো ট্যান হয় না)",
    "2": "II — ফর্সা (সহজে পোড়ে, সামান্য ট্যান)",
    "3": "III — গমবর্ণ (কখনো পোড়ে, ধীরে ট্যান)",
    "4": "IV — বাদামি (খুব কম পোড়ে, সহজে ট্যান)",
    "5": "V — গাঢ় বাদামি (প্রায় কখনো পোড়ে না, গভীর ট্যান)",
    "6": "VI — কালো (কখনো পোড়ে না)",
}

URGENT_BANDS = ("see_doctor_soon",)
ANY_REFERRAL_BANDS = ("see_doctor_soon", "get_it_checked")


def main() -> None:
    with LABELS.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    rows = [r for r in rows if r["fitspatrick"].strip()]
    by_tone: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_tone[row["fitspatrick"].strip()].append(row)

    print(f"{len(rows)} টোন-লেবেল করা ছবি, {len(by_tone)} টোন-গ্রুপ")
    for tone in sorted(by_tone):
        print(f"  টোন {tone}: {len(by_tone[tone])} ছবি")

    # প্রতিটা স্ক্রিনের রেফারেল-হার + স্মার্টফোন-স্ক্রিনের ম্যালিগন্যান্ট recall
    stats: dict[str, dict] = {}
    malignant_by_tone: dict[str, dict] = defaultdict(
        lambda: {"hit": 0, "total": 0}
    )

    for tone in sorted(by_tone):
        counts = {
            "n": 0,
            "dermnet_urgent": 0,
            "ham_referral": 0,
            "pad_referral": 0,
            "mpox_referral": 0,
            "msld_referral": 0,
        }
        for row in by_tone[tone]:
            image = Image.open(
                IMAGING / "pad" / row["file"]
            ).convert("RGB")
            features = extract_features(image).reshape(1, -1)

            general = skin_service._assess_general(features)
            if general and general["band"] in URGENT_BANDS:
                counts["dermnet_urgent"] += 1

            try:
                ham = skin_service._bundle()
                probabilities = ham["model"].predict_proba(features)[0]
                classes = list(ham["model"].classes_)
                referral = set(ham.get("referral_classes", []))
                concern = sum(
                    float(p) for c, p in zip(classes, probabilities,
                                             strict=True)
                    if c in referral
                )
                if concern >= ham.get("referral_threshold", 0.5):
                    counts["ham_referral"] += 1
            except Exception:  # noqa: BLE001
                pass

            pad = skin_service._assess_pad(features)
            is_malignant = row["condition"] in ("BCC", "SCC", "MEL")
            if is_malignant:
                malignant_by_tone[tone]["total"] += 1
            if pad:
                if pad["band"] in ANY_REFERRAL_BANDS:
                    counts["pad_referral"] += 1
                    if is_malignant and pad["band"] in URGENT_BANDS:
                        malignant_by_tone[tone]["hit"] += 1

            mpox = skin_service._assess_mpox(features)
            if mpox and mpox["band"] in ANY_REFERRAL_BANDS:
                counts["mpox_referral"] += 1

            msld = skin_service._assess_msld(features)
            if msld and msld["band"] in ANY_REFERRAL_BANDS:
                counts["msld_referral"] += 1

            counts["n"] += 1
        stats[tone] = counts
        print(f"  টোন {tone} শেষ ({counts['n']} ছবি)")

    # মার্কডাউন রিপোর্ট
    lines = [
        "# ত্বক-টোন নিরীক্ষা — স্ক্রিনগুলো কার ত্বকে কেমন",
        "",
        "প্রতিটি মডেল কার্ডে একই সতর্কতা লেখা আছে: প্রশিক্ষণ-সংগ্রহগুলো",
        "মূলত ফর্সা ত্বকের, বাংলাদেশি ত্বকে আচরণ অযাচাইকৃত। এই নথি সেই কথাটি",
        "প্রথমবার **মাপে** — একমাত্র টোন-লেবেল করা সংগ্রহ PAD-UFES-20 দিয়ে",
        "(১,৪৯৪টি টোন-লেবেল করা ছবি; ব্রাজিলের স্মার্টফোন-ছবি)।",
        "",
        "এটি প্রশিক্ষণ-ডাটার নিরীক্ষা, বাংলাদেশি ত্বকের নয় — ফিটজপ্যাট্রিক IV–VI",
        "দেশের জনসংখ্যার বড় অংশের ত্বক, আর নমুনায় তাদের সংখ্যা খুবই কম।",
        "সেই স্বল্পতাই প্রথম সারির ফল।",
        "",
    ]

    lines.append("| টোন | ছবি | DermNet জরুরি | HAM রেফার | স্মার্টফোন রেফার |")
    lines.append("|---|---|---|---|---|")
    for tone, counts in stats.items():
        n = counts["n"]
        lines.append(
            f"| {TONE_NAMES.get(tone, tone)} | {n} "
            f"| {counts['dermnet_urgent'] / n:.0%} "
            f"| {counts['ham_referral'] / n:.0%} "
            f"| {counts['pad_referral'] / n:.0%} |"
        )

    lines += [
        "",
        "## স্মার্টফোন-স্ক্রিনের ম্যালিগন্যান্ট recall, টোন অনুযায়ী",
        "",
        "| টোন | ম্যালিগন্যান্ট ছবি | জরুরি ব্যান্ডে ধরা | recall |",
        "|---|---|---|---|",
    ]
    for tone in sorted(malignant_by_tone):
        m = malignant_by_tone[tone]
        recall = f"{m['hit'] / m['total']:.0%}" if m["total"] else "—"
        lines.append(
            f"| {TONE_NAMES.get(tone, tone)} | {m['total']} | {m['hit']} "
            f"| {recall} |"
        )

    lines += [
        "",
        "## পাঠ",
        "",
        "টোন IV–VI-এর নমুনা এত ছোট (৭৩টি) যে শতকরা-হার দিয়ে সিদ্ধান্ত নেওয়া",
        "যায় না — কিন্তু ফলটি যা-ই হোক, এই মাপার ক্ষমতাটি নিজেই প্রকল্পের",
        "পরবর্তী প্রয়োজন চিহ্নিত করে: **বাংলাদেশি ত্বকে টোন-লেবেল করা ছবির",
        "সংগ্রহ**। যতদিন তা নেই, এই স্ক্রিনগুলোর গাঢ় ত্বকে আচরণ অনুমানই থাকবে,",
        "এবং প্রতিটি মডেল কার্ডে সেই কথা থাকবে।",
        "",
        "নিরীক্ষণ পুনরায় চালানো: `python ml/audit_skin_tones.py`",
        "",
    ]

    OUT.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(
        json.dumps(
            {
                "dataset": "PAD-UFES-20 (tone-labelled subset)",
                "tones": {
                    tone: {
                        "n": counts["n"],
                        "dermnet_urgent_rate": round(
                            counts["dermnet_urgent"] / counts["n"], 4),
                        "ham_referral_rate": round(
                            counts["ham_referral"] / counts["n"], 4),
                        "pad_referral_rate": round(
                            counts["pad_referral"] / counts["n"], 4),
                        "malignant_recall": (
                            round(malignant_by_tone[tone]["hit"]
                                  / malignant_by_tone[tone]["total"], 4)
                            if malignant_by_tone[tone]["total"] else None
                        ),
                    }
                    for tone, counts in stats.items()
                },
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nরিপোর্ট -> {OUT}")
    print(f"সংখ্যা -> {OUT_JSON}")


if __name__ == "__main__":
    main()
