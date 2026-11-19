# SasthoSetu clinician-review and usability pilot protocol

## Purpose

Collect evidence about usability and clinician agreement for care-navigation.
This is not a diagnostic-validation study and must not be represented as one.

## Minimum safeguards

1. Obtain institutional/clinical approval where required before collection.
2. Obtain explicit participant consent; do not collect unnecessary identifiers.
3. Use only verified doctors for triage review.
4. Store only the minimum assessment data needed for the approved purpose.
5. Do not use a collected case for model retraining until the participant's
   consent, clinician review, de-identification and data-governance checks are
   documented.
6. Treat any emergency concern as a care escalation, not a study interaction.

## Suggested first pilot

| Item | Target |
|---|---|
| Participants | 10–20 consented adults or simulated-vignette users, plus 2+ verified clinicians |
| Setting | Supervised usability session or partner clinic workflow review |
| Inputs | Bangla, Banglish and English scripted vignettes first; real cases only after approval |
| Primary measures | Task completion, time to referral action, comprehension, clinician agreement |
| Safety review | Every emergency band and every clinician override reviewed before reporting |

## Evidence collection workflow

```text
Consent → pseudonymous session → SasthoSetu triage → verified doctor review
→ de-identified aggregate analysis → documented quality gate → optional retraining
```

The application enforces the crucial technical portion: an unverified doctor
cannot create a training-eligible review, and generic user feedback is excluded
from retraining. `ml/retrain_from_feedback.py` only accepts verified-doctor
reviews and retains the existing emergency-recall regression gate.

## Reporting template

Publish aggregate counts, not patient stories or raw symptom text:

| Metric | Value | Denominator | Notes |
|---|---:|---:|---|
| Completed care-pathway tasks |  |  |  |
| Median time to referral action |  |  |  |
| Clinician agreement |  |  | Define agreement before analysis |
| Emergency false negatives |  |  | Review individually; never hide this count |
| Withdrawals / excluded cases |  |  | State reason |

Do not publish results until a responsible clinician has reviewed the wording,
limitations and adverse-event handling.
