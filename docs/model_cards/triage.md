# Model Card — BanglaMed Triage Classifier v1.0

**Task** 5-level severity triage of free-text symptom descriptions in Bangla,
Banglish (romanised), English, and code-switched text.

**Architecture** FeatureUnion[TF-IDF word(1,2), TF-IDF char_wb(2,5)] →
LogisticRegression (calibrated, balanced class weights). Selected over
LinearSVC (0.778) and RandomForest (0.744) on validation macro-F1.

**Training data** 9,000 generated examples (7,201/900/899 split by
block-interleaved assignment), 16 specialties, 12% hard red-flag cases,
languages: bn 42% / banglish 22% / en 16% / mixed 20%. Generator:
`ml/generate_triage_dataset.py` (seed 42, fully reproducible).

**Metrics (held-out test)**
| metric | value |
|---|---|
| macro-F1 | 0.8127 |
| accuracy | 0.792 |
| L5 recall (model alone) | 0.935 |
| L5 recall (with safety rules) | ~1.0 on rule-covered presentations |
Confusion is strictly adjacent-class (no L1↔L5 errors).

**Safety design** 10 rule-based red-flag overrides run *after* the model and
can only raise severity. Confidence is set to 0.98 on override and the
response carries `safety_override_applied: true`.

**Limitations** Synthetic corpus: real patient text is noisier (typos,
dialect, mixed scripts). Lexicon covers ~48 symptoms; out-of-lexicon
complaints fall back to model text features. Not a diagnostic device; outputs
carry a bilingual disclaimer. Clinical validation is required before any
real-world triage use.
