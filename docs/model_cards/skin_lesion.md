# Model Card — Skin Lesion Referral Classifier (2026-11-04 grouped release)

**Task** Decide, from a photograph of a skin lesion, whether it should be seen
by a dermatologist. Seven diagnoses are scored internally; what the patient is
shown is a referral band.

**Architecture** 32 handcrafted features → HistGradientBoosting (balanced class
weights). Validation macro-F1 0.4812, compared with 0.4726 for balanced extra
trees and 0.3545 for multinomial logistic regression.

The features are deliberately handcrafted rather than learned. A dermatologist
assessing a mole looks at asymmetry, border irregularity, colour variation and
diameter — the ABCD rule — and a model built on those same measurements can be
shown to a clinician and argued with. A convolutional network would score
higher and could not be interrogated the same way. For a tool that must be
reviewed before it is trusted, that trade is worth making.

Measured per image: colour statistics in RGB and HSV over the lesion and the
surrounding skin, lesion-to-skin contrast, colour variegation, asymmetry across
both axes, border irregularity, eccentricity, solidity, edge density, intensity
entropy, and blue-white veil fraction.

**Training data** HAM10000 — 10,015 dermatoscopic images from the Medical
University of Vienna. Diagnoses confirmed by histopathology (over half),
follow-up, expert consensus or confocal microscopy. Two exact duplicates were
excluded. Lesion IDs and pixel/perceptual components remain disjoint across
8,029 training, 1,014 validation and 970 test images. Patient IDs are unavailable;
lesion separation does not establish patient-independent evaluation.

| Class | Images | Risk |
|---|---|---|
| nv — melanocytic nevus | 6,705 | benign |
| mel — melanoma | 1,113 | malignant |
| bkl — benign keratosis | 1,099 | benign |
| bcc — basal cell carcinoma | 514 | malignant |
| akiec — actinic keratosis | 327 | precancerous |
| vasc — vascular lesion | 142 | benign |
| df — dermatofibroma | 115 | benign |

**Metrics (frozen grouped test, n=970)**

| metric | value |
|---|---|
| macro AUC | 0.9009 |
| accuracy | 0.7309 |
| macro-F1 (7-class) | 0.4326 |
| **malignant / precancerous recall** | **0.8860** |
| malignant / precancerous precision | 0.3734 |
| specificity | 0.6306 |

The referral decision sums probability across malignant and precancerous
classes, using a threshold chosen on validation for at least 90% recall.
Observed test recall is 88.6%, with a 95% component-bootstrap interval of
83.6%–93.3%. Validation calibration does not guarantee the same recall on new cases.

About 63% of flagged test images have benign source labels. Over-referral and
missed positives both need clinician review. The
[retraining report](../MODEL_RETRAINING_2026-11-04.md) records the complete protocol,
uncertainty and exclusions. Historical scores used a different split and are
not directly comparable.

**Safety design** The response never names a cancer as a conclusion. It returns
one of three bands — see a dermatologist soon, worth getting checked, keep an
eye on it — with the ranked possibilities shown beneath for a reviewing
clinician. Every response carries a bilingual disclaimer. A borderline result
in a patient aged 60 or over is nudged towards review rather than away from it.

**Limitations**

- **Dermatoscopic, not phone photographs.** Every training image was taken
  through a lens pressed against the skin under even lighting. A photograph
  taken on a phone in a village will not look like that, and the model has
  never seen one. This is the largest single caveat.
- **Skin tone.** HAM10000 is overwhelmingly light-skinned European data. Its
  behaviour on Bangladeshi skin is unvalidated and cannot be assumed.
- **Pigmented lesions only.** Infections, burns, fungal rashes and the many
  other skin conditions common in Bangladesh are not represented at all. A
  confident "ordinary mole" on something that is not a mole is possible.
- Non-commercial licence (CC BY-NC 4.0), so images are not redistributed with
  this repository.

**Clinical validation** Not performed. Required before any real-world use, as
for every model in this project. The precondition is a BMDC-registered
dermatology review and evaluation against images captured on the phones people
actually own.

**Citation** Tschandl, P., Rosendahl, C. & Kittler, H. The HAM10000 dataset, a
large collection of multi-source dermatoscopic images of common pigmented skin
lesions. *Scientific Data* 5, 180161 (2018).
