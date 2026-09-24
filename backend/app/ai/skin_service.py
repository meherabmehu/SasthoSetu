# -*- coding: utf-8 -*-
"""Assess a photograph of a skin lesion.

What this returns is a referral decision, not a diagnosis. Naming a specific
cancer to a patient from a phone photograph would be indefensible: the model
was trained on dermatoscopic images taken through a lens pressed against the
skin, and a picture taken on a phone in a village will not look like that.

So the answer given to a patient is one of three bands — see a dermatologist
soon, have it looked at, or keep an eye on it — and every response carries the
bilingual disclaimer. The ranked diagnoses are returned as well, because a
doctor reviewing the case should be able to see what the model actually
thought, but the interface leads with the band.

The referral threshold was chosen on a validation split to catch at least 90%
of malignant and precancerous lesions. That deliberately over-refers: about
four in ten flagged lesions turn out benign. For a screening tool that is the
right way round, and the wording says so.
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

MODEL_VERSION = "sasthosetu-skin-v1.0"

# The maximum photograph accepted. Anything larger is a mistake or an attack;
# the features are computed at 128x128 regardless.
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_DIMENSION = 6000

DIAGNOSES = {
    "akiec": {
        "en": "Actinic keratosis or Bowen's disease",
        "bn": "অ্যাকটিনিক কেরাটোসিস — ত্বকের প্রাক-ক্যানসার অবস্থা",
        "risk": "precancerous",
    },
    "bcc": {
        "en": "Basal cell carcinoma",
        "bn": "ব্যাসাল সেল কার্সিনোমা — এক ধরনের ত্বকের ক্যানসার",
        "risk": "malignant",
    },
    "bkl": {
        "en": "Benign keratosis",
        "bn": "সাধারণ কেরাটোসিস — ক্ষতিকর নয়",
        "risk": "benign",
    },
    "df": {
        "en": "Dermatofibroma",
        "bn": "ডার্মাটোফাইব্রোমা — ত্বকের সাধারণ গুটি, ক্ষতিকর নয়",
        "risk": "benign",
    },
    "mel": {
        "en": "Melanoma",
        "bn": "মেলানোমা — ত্বকের গুরুতর ক্যানসার",
        "risk": "malignant",
    },
    "nv": {
        "en": "Melanocytic nevus (ordinary mole)",
        "bn": "সাধারণ তিল — ক্ষতিকর নয়",
        "risk": "benign",
    },
    "vasc": {
        "en": "Vascular lesion",
        "bn": "রক্তনালীজনিত দাগ — সাধারণত ক্ষতিকর নয়",
        "risk": "benign",
    },
}

BANDS = {
    "see_doctor_soon": {
        "en": "This should be examined by a dermatologist soon.",
        "bn": "এটি দ্রুত একজন চর্মরোগ বিশেষজ্ঞকে দেখানো উচিত।",
        "specialty": "Dermatology",
        "urgent": True,
    },
    "get_it_checked": {
        "en": "Worth having a doctor look at this, without urgency.",
        "bn": "তাড়াহুড়ো নেই, তবে একজন ডাক্তারকে দেখিয়ে নেওয়া ভালো।",
        "specialty": "Dermatology",
        "urgent": False,
    },
    "watch_it": {
        "en": "This looks ordinary. Watch it and see a doctor if it changes "
              "shape, colour or size, or if it bleeds or itches.",
        "bn": "দেখে সাধারণ মনে হচ্ছে। আকার, রং বা গঠন বদলালে, রক্ত পড়লে বা "
              "চুলকালে ডাক্তার দেখান।",
        "specialty": None,
        "urgent": False,
    },
}

DISCLAIMER = {
    "en": ("This is not a diagnosis. A photograph cannot replace an "
           "examination, and this tool was trained on clinical dermatoscope "
           "images rather than phone photographs. If you are worried about a "
           "skin lesion, see a doctor regardless of what this says."),
    "bn": ("এটি রোগ নির্ণয় নয়। ছবি দেখে পরীক্ষা করা সম্ভব নয়, আর এই টুলটি "
           "ক্লিনিকের বিশেষ ক্যামেরার ছবি দিয়ে তৈরি — মোবাইলের ছবি দিয়ে নয়। "
           "ত্বকের কোনো দাগ নিয়ে দুশ্চিন্তা হলে এটি যাই বলুক, ডাক্তার দেখান।"),
}


class SkinModelError(RuntimeError):
    """The trained skin model is missing or unreadable."""


@lru_cache(maxsize=1)
def _bundle() -> dict:
    """The pigmented-lesion model, trained on HAM10000. Optional."""
    path = _ART / "skin_model.joblib"
    if not path.exists():
        raise SkinModelError(
            f"The pigmented lesion model is missing at {path}. Build it with: "
            "python ml/fetch_skin_data.py && python ml/train_skin_model.py"
        )
    return joblib.load(path)


@lru_cache(maxsize=1)
def _general_bundle() -> dict:
    """The general skin condition model, trained on DermNet.

    This one carries the conditions people here actually present with —
    ringworm, scabies, eczema, nail fungus — and is trained on ordinary
    photographs rather than dermatoscope images, so it is the primary model.
    """
    path = _ART / "dermnet_model.joblib"
    if not path.exists():
        raise SkinModelError(
            f"The skin condition model is missing at {path}. Build it with: "
            "python ml/fetch_medical_datasets.py --only dermnet && "
            "python ml/train_dermnet_model.py"
        )
    return joblib.load(path)


@lru_cache(maxsize=1)
def _mpox_bundle() -> dict | None:
    """The viral-rash screen, trained on the MSID photographs.

    Monkeypox, chickenpox and measles are absent from every other dataset we
    serve, so without this screen a rash photograph has no path at all to
    "this could be monkeypox". Optional: absent on a deployment that did not
    build it, present when its artifact ships.
    """
    path = _ART / "mpox_model.joblib"
    if not path.exists():
        return None
    return joblib.load(path)


@lru_cache(maxsize=1)
def _msld_bundle() -> dict | None:
    """The dermatologist-verified viral rash screen, trained on MSLD v2.0.

    A second, independently reviewed collection covering two classes no
    other dataset we serve carries - cowpox and hand-foot-mouth disease.
    Where both viral screens are built they act as two readers: either can
    raise the band, neither can lower it.
    """
    path = _ART / "msld_model.joblib"
    if not path.exists():
        return None
    return joblib.load(path)


@lru_cache(maxsize=1)
def _pad_bundle() -> dict | None:
    """The smartphone lesion screen, trained on PAD-UFES-20.

    Every other lesion model we serve reads dermatoscope images; our users
    photograph a mole with the phone they own, under whatever light they
    have. This screen is trained on exactly that kind of photograph, so it
    is the honest match for that input. Optional, like the others.
    """
    path = _ART / "pad_model.joblib"
    if not path.exists():
        return None
    return joblib.load(path)


# What the smartphone screen calls its classes, in the words the response
# carries.
MSLD_PRESENTATION = {
    "monkeypox": {
        "name_en": "Mpox (monkeypox) — needs urgent review",
        "name_bn": "মাংকিপক্স (এমপক্স) সন্দেহ — দ্রুত পরীক্ষা দরকার",
        "risk": "concerning",
    },
    "cowpox": {
        "name_en": "Cowpox — needs review",
        "name_bn": "কাউপক্স সন্দেহ — পরীক্ষা দরকার",
        "risk": "concerning",
    },
    "hfmd": {
        "name_en": "Hand, foot and mouth disease",
        "name_bn": "হাত-পা-মুখ রোগ",
        "risk": "uncertain",
    },
    "measles": {
        "name_en": "Measles",
        "name_bn": "হাম",
        "risk": "uncertain",
    },
    "chickenpox": {
        "name_en": "Chickenpox (varicella)",
        "name_bn": "জলবসন্ত (চিকেনপক্স)",
        "risk": "uncertain",
    },
    "healthy": {
        "name_en": "Healthy skin",
        "name_bn": "স্বাভাবিক ত্বক",
        "risk": "reassuring",
    },
}

PAD_PRESENTATION = {
    "bcc": {
        "name_en": "Basal cell carcinoma",
        "name_bn": "বেসাল সেল কার্সিনোমা (ত্বকের ক্যানসার)",
        "risk": "malignant",
    },
    "scc": {
        "name_en": "Squamous cell carcinoma",
        "name_bn": "স্কোয়ামাস সেল কার্সিনোমা (ত্বকের ক্যানসার)",
        "risk": "malignant",
    },
    "mel": {
        "name_en": "Melanoma",
        "name_bn": "মেলানোমা (ত্বকের ক্যানসার)",
        "risk": "malignant",
    },
    "ack": {
        "name_en": "Actinic keratosis",
        "name_bn": "অ্যাক্টিনিক কেরাটোসিস (প্রাক-ক্যানসার)",
        "risk": "precancerous",
    },
    "nev": {
        "name_en": "Melanocytic nevus (ordinary mole)",
        "name_bn": "সাধারণ তিল — ক্ষতিকর নয়",
        "risk": "benign",
    },
    "sek": {
        "name_en": "Seborrheic keratosis",
        "name_bn": "সেবোরিক কেরাটোসিস (নিরীহ)",
        "risk": "benign",
    },
}


# What the viral-rash screen calls its classes, in the words the response
# carries. Isolation and contact tracing lose their window when a monkeypox
# photograph is dismissed, so it presents as urgent; the other two viral
# rashes ask for confirmation without the same-day pressure.
MPOX_PRESENTATION = {
    "mpox": {
        "name_en": "Mpox (monkeypox) — needs urgent review",
        "name_bn": "মাংকিপক্স সন্দেহ — দ্রুত পরীক্ষা দরকার",
        "risk": "concerning",
    },
    "chickenpox": {
        "name_en": "Chickenpox (varicella)",
        "name_bn": "জলবসন্ত (চিকেনপক্স)",
        "risk": "uncertain",
    },
    "measles": {
        "name_en": "Measles",
        "name_bn": "হাম",
        "risk": "uncertain",
    },
    "normal": {
        "name_en": "Normal skin",
        "name_bn": "স্বাভাবিক ত্বক",
        "risk": "reassuring",
    },
}


def _generic_concern_screen(bundle: dict, features, presentation: dict) -> dict:
    """Shared scoring for the optional concern-weighted screens.

    Both the viral-rash and the smartphone screens ask the same question -
    a summed, weighted probability against a validation-chosen threshold -
    so they share one implementation rather than two copies that drift.
    """
    model = bundle["model"]
    weight = bundle.get("concern_weight", {})
    threshold = float(bundle.get("referral_threshold", 0.5))
    # sklearn stores the ids it was fitted with; the bundle carries their
    # readable codes.
    code_for = {int(c): str(bundle["classes"][int(c)])
                for c in model.classes_}

    probabilities = model.predict_proba(features)[0]
    classes = list(model.classes_)

    score = 0.0
    for index, cls in enumerate(classes):
        score += float(weight.get(int(cls), 0.0)) * float(probabilities[index])

    if score >= threshold:
        band = "see_doctor_soon"
    elif score >= threshold / 2:
        band = "get_it_checked"
    else:
        band = "watch_it"

    return {
        "band": band,
        "concern": round(score, 4),
        "threshold": threshold,
        "ranked": sorted(
            (
                {
                    "code": code_for[int(cls)],
                    "name_en": presentation.get(
                        code_for[int(cls)], {}
                    ).get("name_en", code_for[int(cls)]),
                    "name_bn": presentation.get(
                        code_for[int(cls)], {}
                    ).get("name_bn", code_for[int(cls)]),
                    "risk": presentation.get(
                        code_for[int(cls)], {}
                    ).get("risk", "unknown"),
                    "likelihood": round(float(probability), 4),
                }
                for cls, probability in zip(classes, probabilities,
                                            strict=True)
            ),
            key=lambda item: -item["likelihood"],
        ),
    }


def _assess_mpox(features) -> dict | None:
    """Referral band and named differential from the viral-rash screen."""
    bundle = _mpox_bundle()
    if bundle is None:
        return None
    return _generic_concern_screen(bundle, features, MPOX_PRESENTATION)


def _assess_pad(features) -> dict | None:
    """Referral band and named differential from the smartphone screen."""
    bundle = _pad_bundle()
    if bundle is None:
        return None
    return _generic_concern_screen(bundle, features, PAD_PRESENTATION)


def _assess_msld(features) -> dict | None:
    """Referral band and named differential from the MSLD screen."""
    bundle = _msld_bundle()
    if bundle is None:
        return None
    return _generic_concern_screen(bundle, features, MSLD_PRESENTATION)


def _assess_general(features) -> dict | None:
    """Referral band from the DermNet model, or None if it is not built."""
    try:
        bundle = _general_bundle()
    except SkinModelError:
        return None

    model = bundle["model"]
    urgent_at = bundle.get("urgent_threshold", 0.3)
    checked_at = bundle.get("checked_threshold", 0.45)

    probabilities = model.predict_proba(features)[0]
    classes = list(model.classes_)
    score = dict(zip(classes, (float(p) for p in probabilities), strict=True))

    urgent = score.get("see_doctor_soon", 0.0)
    checked = urgent + score.get("get_it_checked", 0.0)

    if urgent >= urgent_at:
        band = "see_doctor_soon"
    elif checked >= checked_at:
        band = "get_it_checked"
    else:
        band = "watch_it"

    return {"band": band, "scores": score}


def model_available() -> bool:
    """Whether any skin model can be served, without raising if none can."""
    if (_mpox_bundle() is not None or _pad_bundle() is not None
            or _msld_bundle() is not None):
        return True
    for loader in (_general_bundle, _bundle):
        try:
            loader()
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


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
    if min(image.size) < 32:
        raise ValueError("image is too small to assess")

    return image


BAND_ORDER = ["watch_it", "get_it_checked", "see_doctor_soon"]


def assess_skin_image(payload: bytes, age: Optional[int] = None) -> dict:
    """Assess one photograph and return a referral band with its reasoning.

    Two models may contribute. The DermNet model covers 23 conditions from
    ordinary photographs and is the primary answer. The HAM10000 model is
    narrow — pigmented lesions only — but far better evidenced for malignancy,
    so where it is built and it reads the lesion as concerning, it can raise
    the band. Neither model can lower what the other raised.
    """
    image = _open(payload)
    features = extract_features(image).reshape(1, -1)

    general = _assess_general(features)
    mpox = _assess_mpox(features)
    pad = _assess_pad(features)
    msld = _assess_msld(features)

    ranked: list[dict] = []
    concerning = 0.0
    threshold = 0.5
    band = None

    try:
        bundle = _bundle()
    except SkinModelError:
        bundle = None

    if bundle is not None:
        model = bundle["model"]
        threshold = bundle.get("referral_threshold", 0.5)
        referral_classes = set(bundle.get("referral_classes", []))

        probabilities = model.predict_proba(features)[0]
        classes = list(model.classes_)

        ranked = sorted(
            (
                {
                    "code": code,
                    "name_en": DIAGNOSES.get(code, {}).get("en", code),
                    "name_bn": DIAGNOSES.get(code, {}).get("bn", code),
                    "risk": DIAGNOSES.get(code, {}).get("risk", "unknown"),
                    "likelihood": round(float(probability), 4),
                }
                for code, probability in zip(classes, probabilities,
                                             strict=True)
            ),
            key=lambda item: -item["likelihood"],
        )

        concerning = sum(
            float(probability)
            for code, probability in zip(classes, probabilities, strict=True)
            if code in referral_classes
        )

        if concerning >= threshold:
            band = "see_doctor_soon"
        elif concerning >= threshold / 2:
            band = "get_it_checked"
        else:
            band = "watch_it"

    if general is not None:
        if not ranked:
            # Without the pigmented-lesion model there are no named diagnoses
            # to show, so the bands themselves are reported. A patient still
            # sees what the assessment was based on rather than a bare verdict.
            ranked = sorted(
                (
                    {
                        "code": name,
                        "name_en": BANDS[name]["en"],
                        "name_bn": BANDS[name]["bn"],
                        "risk": ("concerning" if name == "see_doctor_soon"
                                 else "uncertain" if name == "get_it_checked"
                                 else "reassuring"),
                        "likelihood": round(float(score), 4),
                    }
                    for name, score in general["scores"].items()
                ),
                key=lambda item: -item["likelihood"],
            )
            concerning = round(
                float(general["scores"].get("see_doctor_soon", 0.0)), 4
            )

        if band is None:
            band = general["band"]
        else:
            # Take whichever model is more concerned. A pigmented-lesion model
            # shown a fungal infection has nothing useful to say, and the
            # reverse is also true, so the safer reading wins.
            band = max(band, general["band"], key=BAND_ORDER.index)

    if band is None:
        raise SkinModelError(
            "No skin model is built. Build at least one with: "
            "python ml/fetch_medical_datasets.py --only dermnet && "
            "python ml/train_dermnet_model.py"
        )

    def merge_concern_screen(screen, key_name):
        """A screen may only raise the band, never lower it, and its
        strongest candidate joins the differential when it is saying
        anything definite, so the reader sees why the band moved."""
        nonlocal band
        if screen is None:
            return None
        band = max(band, screen["band"], key=BAND_ORDER.index)
        top = screen["ranked"][0] if screen["ranked"] else None
        if top is not None and top["likelihood"] >= 0.3:
            ranked.append(top)
            ranked.sort(key=lambda item: -item["likelihood"])
        return {
            "concern": screen["concern"],
            "threshold": screen["threshold"],
            "top": top,
        }

    mpox_contribution = merge_concern_screen(mpox, "viral")
    pad_contribution = merge_concern_screen(pad, "smartphone")
    msld_contribution = merge_concern_screen(msld, "msld")

    # Older skin carries a higher baseline risk, so a borderline result in an
    # older patient is nudged towards review rather than away from it.
    if age is not None and age >= 60 and band == "watch_it":
        band = "get_it_checked"

    return {
        "band": band,
        "advice": BANDS[band]["en"],
        "advice_bn": BANDS[band]["bn"],
        "recommended_specialty": BANDS[band]["specialty"],
        "urgent": BANDS[band]["urgent"],
        "concern_score": round(concerning, 4),
        "referral_threshold": round(float(threshold), 3),
        "differential": ranked[:4],
        # Which models actually contributed, so a reviewer can tell whether a
        # band came from the broad model, the pigmented-lesion one, or both.
        "models": {
            "general_conditions": general is not None,
            "pigmented_lesions": bundle is not None,
            "viral_rash_screen": mpox is not None,
            "smartphone_lesion_screen": pad is not None,
            "verified_viral_rash_screen": msld is not None,
        },
        "viral_rash": mpox_contribution,
        "smartphone_lesion": pad_contribution,
        "verified_viral_rash": msld_contribution,
        "disclaimer": DISCLAIMER["en"],
        "disclaimer_bn": DISCLAIMER["bn"],
        "model_version": MODEL_VERSION,
    }
