# SasthoSetu API — Quick Reference

Base prefix: `/api/v1` · Interactive docs: `/docs` (Swagger) and `/redoc`
once the server is running (`uvicorn app.main:app --reload`).

This file lists the BanglaMed-AI additions. For the full endpoint set
(auth, patients, doctors, appointments, prescriptions, medical records,
notifications, dashboard, admin, files) use `/docs` — it stays in sync with
the code automatically, which a hand-maintained list here would not.

## BanglaMed-AI

| method | path | notes |
|---|---|---|
| POST | /api/v1/triage | existing rule-based bilingual triage (deterministic safety layer) |
| POST | /api/v1/symptom-checker | deprecated alias of the above |
| POST | /api/v1/ai/triage-ml | multilingual ML triage (bn/banglish/en), red-flag override to EMERGENCY |
| POST | /api/v1/ai/drug-check | BD brand-aware drug interaction screening |
| GET | /api/v1/hospitals/{code}/surge-forecast | 24/48/72h bed-demand forecast per ward |
| GET | /api/v1/population/surveillance | district × disease trend + anomaly alerts |
| POST | /api/v1/ai/feedback | stores corrections for retraining (auth required) |

See `docs/BANGLAMED_AI.md` for how each of these works and
`docs/model_cards/` for accuracy and limitations.
