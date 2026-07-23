# BanglaMed-AI — Technical Overview

The intelligence layer of SasthoSetu: four services behind `/v1` endpoints.

## 1. Multilingual symptom triage — `POST /api/v1/ai/triage-ml`
Pipeline: **extraction → ML classifier → red-flag safety override**.

- *Extraction* (`app/ai/extraction.py`): pure-stdlib entity extractor over a
  curated lexicon of ~48 symptoms with Bangla / Banglish / English surface
  forms; handles negation windows ("জ্বর নেই"), duration in Bangla numerals and
  number-words, qualifiers, and age mentions.
- *Classifier* (`ml/train_triage_model.py`): TF-IDF word(1-2) + char_wb(2-5)
  features, calibrated LogisticRegression, trained on the 9,000-row generated
  corpus. Test macro-F1 **0.813**, accuracy 0.792, errors strictly
  adjacent-class.
- *Safety* (`app/ai/safety.py`): 10 hard-coded red-flag rules (cardiac combo,
  FAST stroke signs, obstetric bleeding, infant fever, snakebite, ...) that
  override the model upward to level 5 with confidence 0.98. Safety rules are
  deliberately rule-based: they must be auditable and never regress silently.

Levels: 1 self-care · 2 teleconsult · 3 GP visit · 4 specialist · 5 emergency.

## 2. Drug-safety screening — `POST /api/v1/ai/drug-check`
Normalises Bangladeshi brand names (Napa → paracetamol, Seclo → omeprazole)
via a 90-entry alias table, then checks all pairs against a 45-pair curated
interaction knowledge base with bilingual advice. Runs automatically on every
prescription created; the report is stored on the prescription row.

## 3. Hospital surge forecasting — `GET /api/v1/hospitals/{code}/surge-forecast`
Per-ward HistGradientBoosting models (24/48/72h horizons) over lag/rolling/
seasonality features from two years of bed-utilization logs across five Dhaka
hospitals. Holdout MAE ≈ **2.9 beds**, beating naive persistence at every
horizon. Alerts fire at ≥90% predicted occupancy.

## 4. Population surveillance — `GET /api/v1/population/surveillance`
EWMA(span=8) baseline + robust z-score anomaly detection over district ×
disease weekly counts. Detector recall **25/25** on injected ground-truth
outbreaks at z ≥ 2.5.

## Feedback loop
`POST /api/v1/ai/feedback` stores corrections in the `ai_feedback` table;
`ml/retrain_from_feedback.py` folds corrected triage examples back into the
training corpus with a no-regression guard.

## Honest scoping
All datasets are **synthetic but principled** (documented generators under
`ml/`); the drug KB is a demo subset; BMDC/DGHS/bKash integrations are mocked.
Model cards in `docs/model_cards/` state limitations explicitly. The Kaggle
pack (`kaggle/`) provides the transformer upgrade path.
