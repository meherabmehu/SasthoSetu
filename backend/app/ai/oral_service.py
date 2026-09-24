# -*- coding: utf-8 -*-
"""Screen a mouth photograph for signs of oral cancer.

Oral cancer is among the commonest cancers in Bangladesh, driven by
betel-quid and tobacco chewing, and it is typically caught late precisely
because the inside of a mouth is not something anyone photographs early.
A health worker with a phone torch can take this photograph; a specialist
to read it is far scarcer.


This is a screen, not a report. It answers one question — does this
photograph show retinopathy that needs an eye specialist — and it is
deliberately set to over-refer. Timely laser treatment can prevent the
blindness that proliferative retinopathy otherwise causes, while an
over-referred healthy retina costs one dilated examination.

It must not be used to rule cancer out. A clear result means the screen
saw nothing, not that the mouth is healthy, and the wording says exactly
that in both languages.
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

MODEL_VERSION = "sasthosetu-oral-v1.0"

MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_DIMENSION = 8000

GRADES = {
    "oral_scc": {
        "en": "Changes that can indicate oral cancer",
        "bn": "মুখের ক্যানসারের মতো পরিবর্তন দেখা যাচ্ছে",
    },
    "oral_normal": {
        "en": "No changes of that kind were seen",
        "bn": "ওই ধরনের পরিবর্তন চোখে পড়েনি",
    },
}

BANDS = {
    "urgent_review": {
        "en": ("This photograph should be seen by a cancer specialist "
               "soon. If there is a sore that has not healed for three "
               "weeks, or difficulty swallowing, go today."),
        "bn": ("এই ছবিটি শীঘ্রই একজন ক্যানসার বিশেষজ্ঞকে দেখানো উচিত। তিন "
               "সপ্তাহেও না শুকোনো ঘা বা গিলতে কষ্ট হলে আজই যান।"),
        "specialty": "ENT / Head & Neck Oncology",
        "urgent": True,
    },
    "doctor_review": {
        "en": ("A doctor should look at this photograph. The screen did "
               "not see clear cancerous changes, which is not the same as "
               "the mouth being healthy - and a sore that lasts three "
               "weeks should be seen regardless of this result."),
        "bn": ("এই ছবিটি একজন চিকিৎসককে দেখানো দরকার। স্ক্রিনে ক্যানসারের "
               "মতো স্পষ্ট পরিবর্তন ধরা পড়েনি — তার মানে এই নয় যে মুখ "
               "সুস্থ। আর তিন সপ্তাহ স্থায়ী যেকোনো ঘা এই ফল যা-ই হোক "
               "দেখানোই উচিত।"),
        "specialty": "ENT / Head & Neck Oncology",
        "urgent": False,
    },
}

DISCLAIMER = {
    "en": ("This is a screening aid, not a diagnosis. It cannot rule "
           "cancer out. Anyone who chews betel quid or tobacco should have "
           "their mouth checked regularly regardless of this result."),
    "bn": ("এটি একটি স্ক্রিনিং সহায়ক, রোগ নির্ণয় নয়। এটি দিয়ে ক্যানসার "
           "বাতিল করা যায় না। পান-জর্দা চোষক যে-ই হোন, এই ফল যা-ই হোক "
           "নিয়মিত মুখ পরীক্ষা করানো উচিত।"),
}


class OralModelError(RuntimeError):
    """The trained retinopathy model is missing or unreadable."""


@lru_cache(maxsize=1)
def _bundle() -> dict:
    path = _ART / "oral_model.joblib"
    if not path.exists():
        raise OralModelError(
            f"The retinopathy model is missing at {path}. Build it with: "
            "python ml/fetch_oral_data.py && python ml/train_oral_model.py"
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


def assess_oral_photo(payload: bytes, age: Optional[int] = None) -> dict:
    """Screen one mouth photograph and return a review band."""
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
