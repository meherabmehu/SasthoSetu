# -*- coding: utf-8 -*-
"""Pre-inference image quality checks for health photographs."""
from __future__ import annotations

import numpy as np
from PIL import Image


class ImageQualityError(ValueError):
    """An uploaded image is too poor to produce a meaningful screen."""


def validate_image_quality(
    image: Image.Image,
    *,
    purpose: str,
    min_mean: float = 12.0,
    max_mean: float = 242.0,
    min_std: float = 5.0,
    min_detail: float = 0.012,
) -> dict:
    """Reject clearly unusable, blank or uniform images before model inference."""
    rgb = np.asarray(image.convert("RGB").resize((128, 128), Image.Resampling.BILINEAR))
    gray = rgb.mean(axis=2)

    mean = float(gray.mean())
    std = float(gray.std())
    gradient_y, gradient_x = np.gradient(gray)
    detail = float(np.mean(np.hypot(gradient_x, gradient_y)))

    reasons: list[str] = []
    if mean < min_mean:
        reasons.append("image_is_too_dark")
    elif mean > max_mean:
        reasons.append("image_is_too_bright")
    if std < min_std:
        reasons.append("image_has_too_little_contrast")
    if detail < min_detail:
        reasons.append("image_is_too_blurry_or_uniform")

    result = {
        "accepted": not reasons,
        "reasons": reasons,
        "purpose": purpose,
        "brightness": round(mean, 2),
        "contrast": round(std, 2),
        "detail": round(detail, 4),
    }
    if reasons:
        raise ImageQualityError(
            "This photograph is too dark, bright, blurry or uniform for a "
            f"reliable {purpose} screen. Use a clear, well-lit image."
        )
    return result
