# -*- coding: utf-8 -*-
"""Measurements taken from a photograph of a skin lesion.

These are the things a dermatologist looks at when assessing a mole, written
down so a machine can measure them and, more importantly, so a clinician can
be shown which measurement drove an answer. The ABCD rule — Asymmetry, Border,
Colour, Diameter — has been taught for decades, and a model built on it can be
argued with. A convolutional network scores higher and cannot.

The same function runs at training time and at serving time, so the two can
never drift apart.

No medical claim is made by this module. It measures pixels.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

# Every image is reduced to this before measuring. Dermatoscopic photographs
# arrive at assorted sizes; the features must not depend on which camera took
# the picture.
WORKING_SIZE = (128, 128)

FEATURE_NAMES = [
    # Colour of the lesion itself
    "lesion_r_mean", "lesion_g_mean", "lesion_b_mean",
    "lesion_r_std", "lesion_g_std", "lesion_b_std",
    "lesion_h_mean", "lesion_s_mean", "lesion_v_mean",
    "lesion_h_std", "lesion_s_std", "lesion_v_std",
    # Colour of the skin around it, and the difference between the two
    "skin_r_mean", "skin_g_mean", "skin_b_mean",
    "contrast_r", "contrast_g", "contrast_b", "contrast_v",
    # Colour variegation: how many distinct shades the lesion contains
    "colour_clusters", "colour_range", "darkest_fraction",
    # Shape
    "area_fraction", "asymmetry_vertical", "asymmetry_horizontal",
    "border_irregularity", "eccentricity", "solidity",
    # Texture
    "edge_density", "intensity_entropy", "local_variance",
    # Blue-white veil, a recognised melanoma sign
    "blue_white_fraction",
]


def _to_hsv(rgb: np.ndarray) -> np.ndarray:
    """Vectorised RGB to HSV on a float array scaled 0-1."""
    maximum = rgb.max(axis=-1)
    minimum = rgb.min(axis=-1)
    delta = maximum - minimum

    hue = np.zeros_like(maximum)
    mask = delta > 1e-6

    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]

    is_red = mask & (maximum == red)
    is_green = mask & (maximum == green)
    is_blue = mask & (maximum == blue)

    with np.errstate(invalid="ignore", divide="ignore"):
        hue[is_red] = ((green - blue)[is_red] / delta[is_red]) % 6
        hue[is_green] = ((blue - red)[is_green] / delta[is_green]) + 2
        hue[is_blue] = ((red - green)[is_blue] / delta[is_blue]) + 4
    hue = hue / 6.0

    saturation = np.zeros_like(maximum)
    nonzero = maximum > 1e-6
    saturation[nonzero] = delta[nonzero] / maximum[nonzero]

    return np.stack([hue, saturation, maximum], axis=-1)


def _segment(gray: np.ndarray) -> np.ndarray:
    """Separate lesion from surrounding skin.

    A lesion is darker than the skin around it, so Otsu's threshold on the
    grey channel separates the two well enough for these measurements. The
    corners are sampled to decide which side of the threshold is skin, because
    a few images are inverted or heavily vignetted.
    """
    values = (gray * 255).astype(np.uint8).ravel()
    histogram = np.bincount(values, minlength=256).astype(np.float64)
    total = histogram.sum()
    if total == 0:
        return np.zeros(gray.shape, dtype=bool)

    probability = histogram / total
    levels = np.arange(256)
    weight_bg = np.cumsum(probability)
    weight_fg = 1.0 - weight_bg

    with np.errstate(invalid="ignore", divide="ignore"):
        mean_bg = np.cumsum(probability * levels) / np.maximum(weight_bg, 1e-9)
        mean_total = (probability * levels).sum()
        mean_fg = (mean_total - np.cumsum(probability * levels)) / np.maximum(
            weight_fg, 1e-9
        )
        between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2

    threshold = int(np.nanargmax(between)) / 255.0
    darker = gray <= threshold

    # The frame corners are almost always skin, so whichever side of the
    # threshold they fall on is the background.
    height, width = gray.shape
    corner = max(2, min(height, width) // 10)
    corners = np.concatenate([
        darker[:corner, :corner].ravel(),
        darker[:corner, -corner:].ravel(),
        darker[-corner:, :corner].ravel(),
        darker[-corner:, -corner:].ravel(),
    ])
    if corners.mean() > 0.5:
        darker = ~darker

    return darker


def _asymmetry(mask: np.ndarray, axis: int) -> float:
    """How much of the lesion fails to overlap its own mirror image."""
    if not mask.any():
        return 0.0
    flipped = np.flip(mask, axis=axis)
    union = (mask | flipped).sum()
    if union == 0:
        return 0.0
    return float((mask ^ flipped).sum() / union)


def _perimeter(mask: np.ndarray) -> float:
    """Count boundary pixels — those inside the mask with a neighbour outside."""
    if not mask.any():
        return 0.0
    padded = np.pad(mask, 1, constant_values=False)
    neighbours = (
        padded[:-2, 1:-1] & padded[2:, 1:-1]
        & padded[1:-1, :-2] & padded[1:-1, 2:]
    )
    return float((mask & ~neighbours).sum())


def extract_features(image: Image.Image) -> np.ndarray:
    """Measure one lesion photograph. Always returns len(FEATURE_NAMES) floats."""
    picture = image.convert("RGB").resize(WORKING_SIZE, Image.BILINEAR)
    rgb = np.asarray(picture, dtype=np.float32) / 255.0

    hsv = _to_hsv(rgb)
    gray = rgb.mean(axis=-1)

    mask = _segment(gray)
    if mask.sum() < 25:
        # Segmentation failed — treat the centre as the lesion rather than
        # returning nothing, so one odd photograph cannot break a batch.
        mask = np.zeros_like(mask)
        height, width = mask.shape
        mask[height // 4:3 * height // 4, width // 4:3 * width // 4] = True

    skin = ~mask
    if skin.sum() < 25:
        skin = ~mask if (~mask).any() else mask

    lesion_rgb = rgb[mask]
    lesion_hsv = hsv[mask]
    skin_rgb = rgb[skin]

    features: list[float] = []

    features.extend(lesion_rgb.mean(axis=0).tolist())
    features.extend(lesion_rgb.std(axis=0).tolist())
    features.extend(lesion_hsv.mean(axis=0).tolist())
    features.extend(lesion_hsv.std(axis=0).tolist())

    skin_mean = skin_rgb.mean(axis=0)
    features.extend(skin_mean.tolist())

    lesion_mean = lesion_rgb.mean(axis=0)
    features.extend((skin_mean - lesion_mean).tolist())
    features.append(float(hsv[skin][..., 2].mean() - lesion_hsv[..., 2].mean()))

    # Colour variegation. A lesion showing several distinct shades is more
    # concerning than a uniform one, which is the "C" in the ABCD rule.
    quantised = (lesion_rgb * 4).astype(np.int32)
    codes = quantised[:, 0] * 25 + quantised[:, 1] * 5 + quantised[:, 2]
    counts = np.bincount(codes.clip(0, 124), minlength=125)
    significant = counts / max(counts.sum(), 1) > 0.05
    features.append(float(significant.sum()))
    features.append(float(lesion_rgb.max() - lesion_rgb.min()))

    lesion_gray = gray[mask]
    features.append(float((lesion_gray < np.percentile(gray, 20)).mean()))

    # Shape
    area = float(mask.sum())
    features.append(area / mask.size)
    features.append(_asymmetry(mask, axis=0))
    features.append(_asymmetry(mask, axis=1))

    perimeter = _perimeter(mask)
    features.append(float(perimeter ** 2 / (4 * np.pi * area))
                    if area > 0 else 0.0)

    rows, cols = np.nonzero(mask)
    if len(rows) > 1:
        height_span = rows.max() - rows.min() + 1
        width_span = cols.max() - cols.min() + 1
        longer = max(height_span, width_span)
        shorter = max(min(height_span, width_span), 1)
        features.append(float(longer / shorter))
        features.append(float(area / (height_span * width_span)))
    else:
        features.extend([1.0, 1.0])

    # Texture
    gradient_y, gradient_x = np.gradient(gray)
    magnitude = np.hypot(gradient_x, gradient_y)
    features.append(float((magnitude > 0.08).mean()))

    histogram = np.histogram(lesion_gray, bins=32, range=(0, 1))[0]
    probability = histogram / max(histogram.sum(), 1)
    probability = probability[probability > 0]
    features.append(float(-(probability * np.log2(probability)).sum()))
    features.append(float(lesion_gray.var()))

    # Blue-white veil: a bluish, low-saturation region inside a lesion is a
    # recognised melanoma sign.
    hue = lesion_hsv[..., 0]
    saturation = lesion_hsv[..., 1]
    value = lesion_hsv[..., 2]
    bluish = (hue > 0.5) & (hue < 0.75) & (saturation > 0.15) & (value > 0.25)
    features.append(float(bluish.mean()))

    vector = np.asarray(features, dtype=np.float32)
    vector = np.nan_to_num(vector, nan=0.0, posinf=0.0, neginf=0.0)

    if len(vector) != len(FEATURE_NAMES):
        raise ValueError(
            f"extracted {len(vector)} features but FEATURE_NAMES lists "
            f"{len(FEATURE_NAMES)} — the two must agree"
        )
    return vector
