# Model Card — BanglaMed Triage Classifier v1.0

**Task** 5-level severity triage of free-text symptom descriptions in Bangla,
Banglish (romanised), English, and code-switched text.

**Architecture** FeatureUnion[TF-IDF word(1,2), TF-IDF char_wb(2,5),
structured clinical features] → LogisticRegression (isotonic-calibrated,
balanced class weights). Selected over LinearSVC (0.706) and RandomForest
(0.693) on validation macro-F1 (0.908).

The structured block supplies symptom indicators, highest symptom acuity,
symptom count, qualifier, duration band, age band and red-flag indicators,
built by the same extractor that runs at serving time so training and inference
cannot diverge. Age in particular arrives as a request field rather than in the
note, so a text-only model is blind to it.

**Training data** 9,000 generated examples (7,201/900/899 split by
block-interleaved assignment), 16 specialties, 12% hard red-flag cases,
languages: bn 42% / banglish 22% / en 16% / mixed 20%. Generator:
`ml/generate_triage_dataset.py` (seed 42, fully reproducible).

**Metrics (held-out test, n=900)**
| metric | value |
|---|---|
| macro-F1 | 0.8397 |
| accuracy | 0.8589 |
| L5 recall (model alone) | 0.9748 |
| L5 recall (with safety rules) | ~1.0 on rule-covered presentations |
| errors spanning ≥3 severity bands | 0 |

No case is misclassified by three or more bands, so the model never confuses
self-care with an emergency. Remaining error is adjacent-band disagreement.

Retraining is gated: a new artifact is promoted only if macro-F1 holds within
0.01 and emergency recall does not fall at all.

**Safety design** 10 rule-based red-flag overrides run *after* the model and
can only raise severity. Confidence is set to 0.98 on override and the
response carries `safety_override_applied: true`.

**Limitations** Synthetic corpus: real patient text is noisier (typos,
dialect, mixed scripts). Lexicon covers ~48 symptoms; out-of-lexicon
complaints fall back to model text features. Not a diagnostic device; outputs
carry a bilingual disclaimer. Clinical validation is required before any
real-world triage use.
