# -*- coding: utf-8 -*-
"""Screen a retina photograph for diabetic retinopathy.

Diabetes prevalence among Bangladeshi adults has passed ten percent, and
diabetic retinopathy is one of the leading causes of preventable blindness
among them. A fundus photograph can be taken with a handheld camera in an
upazila vision centre; an ophthalmologist to read it is far scarcer.

This is a screen, not a report. It answers one question — does this
photograph show retinopathy that needs an eye specialist — and it is
deliberately set to over-refer. Timely laser treatment can prevent the
blindness that proliferative retinopathy otherwise causes, while an
over-referred healthy retina costs one dilated examination.

It must not be used to rule retinopathy out. A clear result means the
screen saw nothing, not that the eyes are healthy, and the wording says
exactly that in both languages.
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

MODEL_VERSION = "sasthosetu-dr-v1.0"

MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_DIMENSION = 8000

GRADES = {
    "proliferative": {
        "en": "Changes that can indicate proliferative retinopathy",
        "bn": "প্রলিফারেটিভ রেটিনোপ্যাথির মতো পরিবর্তন দেখা যাচ্ছে",
    },
    "severe": {
        "en": "Changes that can indicate severe retinopathy",
        "bn": "গুরুতর রেটিনোপ্যাথির মতো পরিবর্তন দেখা যাচ্ছে",
    },
    "moderate": {
        "en": "Changes that can indicate moderate retinopathy",
        "bn": "মাঝারি রেটিনোপ্যাথির মতো পরিবর্তন দেখা যাচ্ছে",
    },
    "mild": {
        "en": "Changes that can indicate mild retinopathy",
        "bn": "হালকা রেটিনোপ্যাথির মতো পরিবর্তন দেখা যাচ্ছে",
    },
    "healthy": {
        "en": "No changes of that kind were seen",
        "bn": "ওই ধরনের পরিবর্তন চোখে পড়েনি",
    },
}

BANDS = {
    "urgent_review": {
        "en": ("This photograph should be seen by an eye specialist soon. "
               "If vision has become blurry, dark-spotted or sudden loss "
               "occurred, go today."),
        "bn": ("এই ছবিটি শীঘ্রই একজন চক্ষু বিশেষজ্ঞকে দেখানো উচিত। দৃষ্টি "
               "ঝাপসা হলে, কালো ছোপ পড়লে বা হঠাৎ কমে গেলে আজই যান।"),
        "specialty": "Ophthalmology",
        "urgent": True,
    },
    "doctor_review": {
        "en": ("A doctor should look at this photograph. The screen did not "
               "see clear sight-threatening changes, which is not the same "
               "as the eyes being healthy."),
        "bn": ("এই ছবিটি একজন চিকিৎসককে দেখানো দরকার। স্ক্রিনে দৃষ্টির "
               "জন্য হুমকির মতো স্পষ্ট পরিবর্তন ধরা পড়েনি — তার মানে এই "
               "নয় যে চোখ সুস্থ।"),
        "specialty": "Ophthalmology",
        "urgent": False,
    },
}

DISCLAIMER = {
    "en": ("This is a screening aid, not an eye examination. It cannot rule "
           "retinopathy out. Every diabetic should have a full eye "
           "examination at least once a year regardless of this result."),
    "bn": ("এটি একটি স্ক্রিনিং সহায়ক, চোখ পরীক্ষা নয়। এটি দিয়ে "
           "রেটিনোপ্যাথি বাতিল করা যায় না। ফল যা-ই হোক, প্রতিটি ডায়াবেটিক "
           "রোগীর বছরে অন্তত একবার পূর্ণাঙ্গ চোখ পরীক্ষা করানো উচিত।"),
}


class EyeModelError(RuntimeError):
    """The trained retinopathy model is missing or unreadable."""


@lru_cache(maxsize=1)
def _bundle() -> dict:
    path = _ART / "dr_model.joblib"
    if not path.exists():
        raise EyeModelError(
            f"The retinopathy model is missing at {path}. Build it with: "
            "python ml/fetch_dr_data.py && python ml/train_dr_model.py"
        )
    return joblib.load(path)


def model_available() -> bool:
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


def assess_eye_photo(payload: bytes, age: Optional[int] = None) -> dict:
    """Screen one fundus photograph and return a review band."""
    bundle = _bundle()
    model = bundle["model"]
    weight = bundle.get("concern_weight", {})
    threshold = float(bundle.get("referral_threshold", 0.5))
    code_for = {int(c): str(bundle["classes"][int(c)])
                for c in model.classes_}

    image = _open(payload)
    features = extract_features(image).reshape(1, -1)

    probabilities = model.predict_proba(features)[0]
    classes = list(model.classes_)

    concern = 0.0
    for index, cls in enumerate(classes):
        concern += float(weight.get(int(cls), 0.0)) * float(
            probabilities[index]
        )

    band = "urgent_review" if concern >= threshold else "doctor_review"

    ranked = sorted(
        (
            {
                "finding": code_for[int(cls)],
                "name_en": GRADES.get(
                    code_for[int(cls)], {}
                ).get("en", code_for[int(cls)]),
                "name_bn": GRADES.get(
                    code_for[int(cls)], {}
                ).get("bn", code_for[int(cls)]),
                "likelihood": round(float(probability), 4),
            }
            for cls, probability in zip(classes, probabilities, strict=True)
        ),
        key=lambda item: -item["likelihood"],
    )

    return {
        "band": band,
        "advice": BANDS[band]["en"],
        "advice_bn": BANDS[band]["bn"],
        "urgent": BANDS[band]["urgent"],
        "concern_score": round(concern, 4),
        "threshold": round(threshold, 3),
        "findings": ranked,
        "recommended_specialty": BANDS[band]["specialty"],
        "disclaimer": DISCLAIMER["en"],
        "disclaimer_bn": DISCLAIMER["bn"],
        "model_version": MODEL_VERSION,
    }
