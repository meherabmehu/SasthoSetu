# BanglaMed-AI — Technical Overview

The intelligence layer of SasthoSetu: four services behind `/v1` endpoints.

## 1. Multilingual symptom triage — `POST /api/v1/ai/triage-ml`
Pipeline: **extraction → ML classifier → red-flag safety override**.

- *Extraction* (`app/ai/extraction.py`): pure-stdlib entity extractor over a
  curated lexicon of ~48 symptoms with Bangla / Banglish / English surface
  forms; handles negation windows ("জ্বর নেই"), duration in Bangla numerals and
  number-words, qualifiers, and age mentions.
- *Classifier* (`ml/train_triage_model.py`): TF-IDF word(1-2) + char_wb(2-5)
  features **plus structured clinical signals** (symptom indicators, highest
  acuity, duration band, age band, red-flag flags) from `app/ai/features.py`,
  calibrated LogisticRegression selected against LinearSVC and RandomForest on
  validation macro-F1. Trained on the 9,000-row generated corpus.
  Test macro-F1 **0.840**, accuracy 0.859, emergency recall **0.975**, and
  **zero** errors spanning three or more severity bands.

  The structured block matters: age arrives as a request field rather than in
  the note text, so a text-only model cannot see it. Adding it moved macro-F1
  from 0.52 to 0.84.
- *Safety* (`app/ai/safety.py`): 10 hard-coded red-flag rules (cardiac combo,
  FAST stroke signs, obstetric bleeding, infant fever, snakebite, ...) that
  override the model upward to level 5 with confidence 0.98. Safety rules are
  deliberately rule-based: they must be auditable and never regress silently.

Levels: 1 self-care · 2 teleconsult · 3 GP visit · 4 specialist · 5 emergency.

## 2. Drug-safety screening — `POST /api/v1/ai/drug-check`
Normalises Bangladeshi brand names (Napa → paracetamol, Seclo → omeprazole)
via a 152-entry alias table covering 73 generics, then checks all pairs against
an 81-pair curated interaction knowledge base with bilingual advice. Also flags
**duplicate therapy** where two brands share one generic — a real overdose
route that brand-first prescribing hides. Runs automatically whenever a
prescription is issued, before it is signed; the report is stored on the
prescription record.

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

## Feedback loop
`POST /api/v1/triage/sessions/{id}/review` records a clinician confirming or
overriding an assessment, and `POST /api/v1/ai/feedback` accepts submitted
corrections. `ml/retrain_from_feedback.py` folds both into the corpus.

Corrections enter the **training** split only — letting them reach the test
split would grade the model on the examples it was just handed. A retrained
model is promoted only if macro-F1 holds within tolerance and emergency recall
does not fall at all; otherwise the previous corpus and artifact are restored.

## Honest scoping
All corpora are **synthetic but principled**, generated from the same lexicon
the runtime extractor uses (`ml/generate_*.py`, seed 42). The drug knowledge
base is a curated set covering common Bangladeshi outpatient prescribing, not
an exhaustive pharmacopoeia. BMDC, DGHS and payment-gateway integrations run in
clearly labelled sandbox mode until real credentials are supplied.

**Clinical validation against real patient data, under ethics approval and a
registered clinical advisory board, is required before any real-world triage
use.** Model cards in `docs/model_cards/` state each model's limitations.
