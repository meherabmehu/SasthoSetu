# -*- coding: utf-8 -*-
"""BanglaMed-AI Triage Service.

End-to-end pipeline implementing POST /v1/triage from the platform document
(section 13.1):

    raw note (bn/en/banglish/mixed)
      -> entity extraction (symptoms, duration, qualifier, age)
      -> ML severity classification with calibrated confidence
      -> hard-coded red-flag safety override (never downgraded)
      -> care pathway + specialty recommendation + bilingual disclaimer

The model file is loaded once at import and reused across requests.
Every response carries a confidence score and a clinical disclaimer —
BanglaMed-AI is decision support, never autonomous care direction.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import joblib
import pandas as pd

from .extraction import extract
from .lexicon import CARE_PATHWAYS, SYMPTOMS, TRIAGE_LABELS
from .safety import apply_safety_override, check_red_flags

_ART = Path(__file__).resolve().parent / "artifacts"

MODEL_VERSION = "banglamed-triage-v1.1"

DISCLAIMER = {
    "en": ("BanglaMed-AI is a decision-support tool, not a medical diagnosis. "
           "Always consult a registered physician. In an emergency go to the "
           "nearest hospital immediately."),
    "bn": ("বাংলামেড-এআই একটি সিদ্ধান্ত-সহায়ক টুল, চিকিৎসা নির্ণয় নয়। "
           "সবসময় রেজিস্টার্ড চিকিৎসকের পরামর্শ নিন। জরুরি অবস্থায় এখনই "
           "নিকটস্থ হাসপাতালে যান।"),
}


@lru_cache(maxsize=1)
def _model():
    return joblib.load(_ART / "triage_model.joblib")


def _specialties(symptoms: list[str], flags: list[dict]) -> list[str]:
    if flags:
        return ["Emergency"]
    ranked = sorted(symptoms, key=lambda s: SYMPTOMS[s]["level"], reverse=True)
    seen: list[str] = []
    for s in ranked:
        sp = SYMPTOMS[s]["specialty"]
        if sp not in seen:
            seen.append(sp)
    return seen[:3] or ["General Medicine"]


def triage(notes: str, age: Optional[int] = None,
           language_hint: Optional[str] = None) -> dict:
    """Run the full BanglaMed-AI triage pipeline on a free-text note."""
    ents = extract(notes or "")
    eff_age = age if age is not None else ents.age

    model = _model()
    frame = pd.DataFrame([{"text": notes or "", "age": eff_age}])
    proba = model.predict_proba(frame)[0]
    classes = list(model.classes_)
    ml_level = int(classes[int(proba.argmax())])
    confidence = float(proba.max())

    flags = check_red_flags(ents.symptoms, eff_age)
    level = apply_safety_override(ml_level, flags)
    if flags:                      # rule override is deterministic, not probabilistic
        confidence = max(confidence, 0.98)

    return {
        "severity_level": level,
        "severity_label": TRIAGE_LABELS[level],
        "ml_predicted_level": ml_level,
        "safety_override_applied": bool(flags) and level != ml_level,
        "recommended_pathway": CARE_PATHWAYS[level],
        "matched_specialties": _specialties(ents.symptoms, flags),
        "confidence_score": round(confidence, 3),
        "safety_flags": flags,
        "entities": ents.to_dict(),
        "level_probabilities": {int(c): round(float(p), 3)
                                for c, p in zip(classes, proba)},
        "disclaimer": DISCLAIMER,
        "model_version": MODEL_VERSION,
    }


if __name__ == "__main__":
    import json
    for note in [
        "বুকে ব্যথা, শ্বাস নিতে কষ্ট, দুই দিন ধরে জ্বর",
        "amar 3 din dhore halka kashi r shordi",
        "হঠাৎ মুখ বেঁকে গেছে, কথা জড়িয়ে যাচ্ছে",
        "mild headache since yesterday",
    ]:
        r = triage(note)
        print(f"\n>> {note}\n   level={r['severity_level']} "
              f"({r['severity_label']}) conf={r['confidence_score']} "
              f"flags={[f['flag'] for f in r['safety_flags']]} "
              f"spec={r['matched_specialties']}")
