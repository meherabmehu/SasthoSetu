# -*- coding: utf-8 -*-
"""Screen a chest X-ray for signs of pneumonia.

Pneumonia is among the leading causes of death in children under five in
Bangladesh. Upazila health complexes can take a film; a radiologist to read it
is often a district away, and a child can deteriorate in that time.

This is a screen, not a report. It answers one question — does this film look
like pneumonia — and it is deliberately set to over-refer. A film that might be
pneumonia is escalated; a normal film wrongly escalated costs a review, while a
missed pneumonia can cost a life.

It must not be used to rule pneumonia out. A clear result means the screen saw
nothing, not that the child is well, and the wording says exactly that in both
languages.
"""
from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path
from typing import Optional

import joblib
from PIL import Image

from .skin_features import extract_features

_ART = Path(__file__).resolve().parent / "artifacts"

MODEL_VERSION = "sasthosetu-cxr-v1.0"

MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_DIMENSION = 8000

FINDINGS = {
    "pneumonia": {
        "en": "Changes that can indicate pneumonia",
        "bn": "নিউমোনিয়ার মতো পরিবর্তন দেখা যাচ্ছে",
    },
    "normal": {
        "en": "No changes of that kind were seen",
        "bn": "ওই ধরনের পরিবর্তন চোখে পড়েনি",
    },
}

BANDS = {
    "urgent_review": {
        "en": ("This film should be read by a doctor today. If the patient is "
               "a child who is breathing fast, drawing in the chest, or not "
               "feeding, go to a hospital now rather than waiting."),
        "bn": ("এই ফিল্মটি আজই একজন চিকিৎসককে দেখানো উচিত। শিশুর যদি দ্রুত "
               "শ্বাস চলে, বুক দেবে যায়, বা খাওয়া বন্ধ করে দেয় — অপেক্ষা না "
               "করে এখনই হাসপাতালে নিন।"),
        "urgent": True,
    },
    "doctor_review": {
        "en": ("A doctor should look at this film. The screen did not see "
               "clear signs, which is not the same as the film being normal."),
        "bn": ("এই ফিল্মটি একজন চিকিৎসককে দেখানো দরকার। স্ক্রিনে স্পষ্ট কিছু "
               "ধরা পড়েনি — তার মানে এই নয় যে ফিল্মটি স্বাভাবিক।"),
        "urgent": False,
    },
}

DISCLAIMER = {
    "en": ("This is a screening aid, not a radiology report. It cannot rule "
           "pneumonia out, and it was trained on paediatric films from one "
           "hospital. Every film still needs a qualified reader."),
    "bn": ("এটি একটি স্ক্রিনিং সহায়ক, রেডিওলজি রিপোর্ট নয়। এটি দিয়ে "
           "নিউমোনিয়া বাতিল করা যায় না, আর এটি একটি হাসপাতালের শিশুদের "
           "ফিল্ম দিয়ে তৈরি। প্রতিটি ফিল্ম যোগ্য চিকিৎসককে দেখাতেই হবে।"),
}


class XrayModelError(RuntimeError):
    """The trained chest X-ray model is missing or unreadable."""


@lru_cache(maxsize=1)
def _bundle() -> dict:
    path = _ART / "chest_xray_model.joblib"
    if not path.exists():
        raise XrayModelError(
            f"The chest X-ray model is missing at {path}. Build it with: "
            "python ml/fetch_medical_datasets.py --only pneumonia && "
            "python ml/train_chest_xray_model.py"
        )
    return joblib.load(path)


@lru_cache(maxsize=1)
def _tb_bundle() -> dict | None:
    """The tuberculosis screen, trained on the combined film collection.

    Optional: absent on a deployment that did not build it. Tuberculosis
    had no class in the pneumonia model's vocabulary at all, so before this
    screen a film full of upper-lobe cavities could only ever read as
    "nothing clearly wrong".
    """
    path = _ART / "tb_model.joblib"
    if not path.exists():
        return None
    return joblib.load(path)


# What the TB screen calls its classes, in the words the response carries.
TB_PRESENTATION = {
    "tuberculosis": {
        "name_en": "Tuberculosis — needs a confirmatory test",
        "name_bn": "যক্ষ্মা (টিবি) সন্দেহ — কফ পরীক্ষা দরকার",
    },
    "pneumonia": {
        "name_en": "Pneumonia",
        "name_bn": "নিউমোনিয়া",
    },
    "covid19": {
        "name_en": "COVID-19 pattern",
        "name_bn": "কোভিড-১৯ সন্দেহ",
    },
    "normal": {
        "name_en": "Normal",
        "name_bn": "স্বাভাবিক",
    },
}


def _screen_tb(features) -> dict | None:
    """Concern score and named findings from the TB screen."""
    bundle = _tb_bundle()
    if bundle is None:
        return None

    model = bundle["model"]
    weight = bundle.get("concern_weight", {})
    threshold = float(bundle.get("referral_threshold", 0.5))
    # sklearn stores the ids it was fitted with; the bundle carries their
    # readable codes.
    code_for = {int(c): str(bundle["classes"][int(c)])
                for c in model.classes_}

    probabilities = model.predict_proba(features)[0]
    classes = list(model.classes_)

    concern = 0.0
    for index, cls in enumerate(classes):
        concern += float(weight.get(int(cls), 0.0)) * float(probabilities[index])

    return {
        "concern": round(concern, 4),
        "threshold": round(threshold, 3),
        "ranked": sorted(
            (
                {
                    "finding": code_for[int(cls)],
                    "name_en": TB_PRESENTATION.get(
                        code_for[int(cls)], {}
                    ).get("name_en", code_for[int(cls)]),
                    "name_bn": TB_PRESENTATION.get(
                        code_for[int(cls)], {}
                    ).get("name_bn", code_for[int(cls)]),
                    "likelihood": round(float(probability), 4),
                }
                for cls, probability in zip(classes, probabilities,
                                            strict=True)
            ),
            key=lambda item: -item["likelihood"],
        ),
    }


def model_available() -> bool:
    if _tb_bundle() is not None:
        return True
    try:
        _bundle()
    except Exception:  # noqa: BLE001
        return False
    return True


def _open(payload: bytes) -> Image.Image:
    if len(payload) > MAX_IMAGE_BYTES:
        raise ValueError(
            f"image is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB"
        )
    try:
        image = Image.open(io.BytesIO(payload))
        image.load()
    except Exception as error:  # noqa: BLE001
        raise ValueError("that file could not be read as an image") from error

    if max(image.size) > MAX_DIMENSION:
        raise ValueError("image dimensions are implausibly large")
    if min(image.size) < 64:
        raise ValueError("image is too small to assess")
    return image


def assess_chest_xray(payload: bytes, age: Optional[int] = None) -> dict:
    """Screen one chest film and return a review band."""
    bundle = _bundle()
    model = bundle["model"]
    threshold = bundle.get("threshold", 0.5)

    image = _open(payload)
    features = extract_features(image).reshape(1, -1)

    probabilities = model.predict_proba(features)[0]
    classes = list(model.classes_)
    score = dict(zip(classes, (float(p) for p in probabilities), strict=True))
    pneumonia = score.get("pneumonia", 0.0)

    band = "urgent_review" if pneumonia >= threshold else "doctor_review"

    # Pneumonia kills fastest in the very young, so a borderline film in an
    # infant is escalated rather than left for a routine review.
    if age is not None and age < 5 and pneumonia >= threshold / 2:
        band = "urgent_review"

    tb_screen = _screen_tb(features)
    if tb_screen is not None and tb_screen["concern"] >= tb_screen["threshold"]:
        # A concerning tuberculosis reading escalates the band the same way
        # a concerning pneumonia reading does: both films need a doctor
        # today, and the TB one additionally needs a confirmatory test.
        band = "urgent_review"

    ranked = sorted(
        (
            {
                "finding": name,
                "name_en": FINDINGS.get(name, {}).get("en", name),
                "name_bn": FINDINGS.get(name, {}).get("bn", name),
                "likelihood": round(value, 4),
            }
            for name, value in score.items()
        ),
        key=lambda item: -item["likelihood"],
    )

    return {
        "band": band,
        "advice": BANDS[band]["en"],
        "advice_bn": BANDS[band]["bn"],
        "urgent": BANDS[band]["urgent"],
        "pneumonia_score": round(pneumonia, 4),
        "threshold": round(float(threshold), 3),
        "findings": ranked,
        "tuberculosis_screen": (
            {
                "concern": tb_screen["concern"],
                "threshold": tb_screen["threshold"],
                "top": tb_screen["ranked"][0] if tb_screen["ranked"] else None,
            }
            if tb_screen is not None
            else None
        ),
        "recommended_specialty": "Pulmonology",
        "disclaimer": DISCLAIMER["en"],
        "disclaimer_bn": DISCLAIMER["bn"],
        "model_version": MODEL_VERSION,
    }
