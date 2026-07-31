# -*- coding: utf-8 -*-
"""Structured clinical features for the triage classifier.

Text n-grams alone cannot see everything that determines triage severity. Age
is supplied by the client as a separate field rather than being written into
the note, duration is often implicit, and red-flag combinations depend on which
symptoms co-occur rather than on surface wording.

This module turns a raw note plus optional age into the structured signals the
classifier needs, using exactly the same extractor that runs at serving time so
training and inference cannot diverge.

The features are deliberately interpretable: symptom indicators, the highest
symptom acuity present, symptom count, qualifier, duration band, age band and
red-flag indicators. Nothing here is learned, so the same code path is safe to
run inside the request cycle.
"""
from __future__ import annotations

from typing import Iterable, Optional

import numpy as np

from .extraction import extract
from .lexicon import SYMPTOMS
from .safety import RED_FLAG_RULES, check_red_flags

SYMPTOM_INDEX = {name: i for i, name in enumerate(sorted(SYMPTOMS))}
FLAG_INDEX = {rule["flag"]: i for i, rule in enumerate(RED_FLAG_RULES)}

QUALIFIER_INDEX = {"severe": 0, "mild": 1, "intermittent": 2}

FEATURE_NAMES = (
    [f"symptom__{name}" for name in sorted(SYMPTOMS)]
    + [f"flag__{rule['flag']}" for rule in RED_FLAG_RULES]
    + [
        "max_level",
        "mean_level",
        "symptom_count",
        "has_symptom",
        "qualifier_severe",
        "qualifier_mild",
        "qualifier_intermittent",
        "duration_known",
        "duration_days",
        "duration_acute",
        "duration_subacute",
        "duration_chronic",
        "age_known",
        "age_norm",
        "age_infant",
        "age_child",
        "age_adult",
        "age_elderly",
        "red_flag_any",
        "negated_count",
    ]
)


def _row(text: str, age: Optional[float]) -> np.ndarray:
    result = extract(text or "")
    symptoms = result.symptoms

    effective_age: Optional[int] = None
    if age is not None and not (isinstance(age, float) and np.isnan(age)):
        effective_age = int(age)
    elif result.age is not None:
        effective_age = result.age

    vector = np.zeros(len(FEATURE_NAMES), dtype=np.float32)

    for symptom in symptoms:
        position = SYMPTOM_INDEX.get(symptom)
        if position is not None:
            vector[position] = 1.0

    offset = len(SYMPTOM_INDEX)
    flags = check_red_flags(symptoms, effective_age)
    for flag in flags:
        position = FLAG_INDEX.get(flag["flag"])
        if position is not None:
            vector[offset + position] = 1.0

    base = offset + len(FLAG_INDEX)
    levels = [SYMPTOMS[s]["level"] for s in symptoms if s in SYMPTOMS]

    vector[base + 0] = max(levels) if levels else 0.0
    vector[base + 1] = float(np.mean(levels)) if levels else 0.0
    vector[base + 2] = float(len(symptoms))
    vector[base + 3] = 1.0 if symptoms else 0.0

    if result.qualifier in QUALIFIER_INDEX:
        vector[base + 4 + QUALIFIER_INDEX[result.qualifier]] = 1.0

    days = result.duration_days
    vector[base + 7] = 1.0 if days is not None else 0.0
    if days is not None:
        vector[base + 8] = min(float(days), 60.0) / 60.0
        vector[base + 9] = 1.0 if days <= 2 else 0.0
        vector[base + 10] = 1.0 if 3 <= days <= 13 else 0.0
        vector[base + 11] = 1.0 if days >= 14 else 0.0

    vector[base + 12] = 1.0 if effective_age is not None else 0.0
    if effective_age is not None:
        vector[base + 13] = min(float(effective_age), 100.0) / 100.0
        vector[base + 14] = 1.0 if effective_age < 1 else 0.0
        vector[base + 15] = 1.0 if 1 <= effective_age < 5 else 0.0
        vector[base + 16] = 1.0 if 18 <= effective_age < 65 else 0.0
        vector[base + 17] = 1.0 if effective_age >= 65 else 0.0

    vector[base + 18] = 1.0 if flags else 0.0
    vector[base + 19] = float(len(result.negated_symptoms))

    return vector


def text_column(frame):
    """Select the free-text column from the input frame.

    Defined here rather than in the training script so the fitted pipeline can
    be unpickled by the serving process, which never imports ml/.
    """
    return frame["text"].astype(str)


def clinical_feature_matrix(frame) -> np.ndarray:
    """Build the clinical feature matrix for a frame with text and age columns.

    Accepts a pandas DataFrame (training) or any object exposing the same two
    columns, so the serving path can pass a single-row frame unchanged.
    """
    texts: Iterable
    ages: Iterable

    if hasattr(frame, "columns"):
        texts = frame["text"].tolist()
        ages = (
            frame["age"].tolist()
            if "age" in frame.columns
            else [None] * len(texts)
        )
    else:
        texts = [row[0] for row in frame]
        ages = [row[1] for row in frame]

    return np.vstack(
        [_row(text, age) for text, age in zip(texts, ages, strict=False)]
    )
