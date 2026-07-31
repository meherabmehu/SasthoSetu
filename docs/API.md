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

## Clinical workflow

| method | path | notes |
|---|---|---|
| POST | /api/v1/triage/sessions | run and store a triage assessment (works unauthenticated) |
| GET | /api/v1/triage/sessions/mine | the caller's triage history |
| POST | /api/v1/triage/sessions/{id}/review | clinician confirms or overrides an assessment |
| GET | /api/v1/doctors/match | rank verified doctors, optionally from a triage session |
| POST | /api/v1/consultations | open a consultation against an appointment |
| POST | /api/v1/consultations/{id}/close | sign and seal the encounter |
| POST | /api/v1/prescriptions/issue | issue a signed multi-item prescription |
| POST | /api/v1/prescriptions/verify | pharmacy check: genuine, unexpired, not dispensed |
| POST | /api/v1/prescriptions/dispense | record a single-use dispensing |

## Hospitals and capacity

| method | path | notes |
|---|---|---|
| GET | /api/v1/hospitals | facility directory with bed totals |
| GET | /api/v1/hospitals/nearby | emergency routing by availability then distance |
| PATCH | /api/v1/wards/{id}/bed-status | update occupancy (staff scoped to their facility) |
| GET | /api/v1/wards/{id}/history | append-only capacity history |

## Labs, pharmacies and payments

| method | path | notes |
|---|---|---|
| POST | /api/v1/lab-orders | order a test from a verified lab |
| POST | /api/v1/lab-orders/{id}/result | lab uploads a result |
| PATCH | /api/v1/lab-orders/{id}/consent | patient grants or withdraws clinician access |
| GET | /api/v1/pharmacies/search | stock search resolving brands to generics |
| POST | /api/v1/payments/checkout | idempotent checkout; amount derived server-side |
| POST | /api/v1/payments/callback | signature-verified gateway webhook |
| GET | /api/v1/payments/reconciliation | settlement report (admin) |

## Rural access

| method | path | notes |
|---|---|---|
| POST | /api/v1/rural/sms/triage | inbound SMS; returns a reply within the segment budget |
| GET | /api/v1/rural/ivr/menu | IVR prompt and valid keys |
| POST | /api/v1/rural/ivr/select | apply a keypress; escalates emergencies to an operator |
| POST | /api/v1/rural/chw/batch | offline community health worker assessments |

## FHIR R4

| method | path | notes |
|---|---|---|
| GET | /api/v1/fhir/metadata | CapabilityStatement |
| GET | /api/v1/fhir/Patient/{id} | Patient resource |
| GET | /api/v1/fhir/Patient/{id}/$everything | complete record as one Bundle |
| GET | /api/v1/fhir/MedicationRequest?patient= | prescriptions as MedicationRequest |
| GET | /api/v1/fhir/DiagnosticReport?patient= | lab orders as DiagnosticReport |

## Error conventions

- `503` with the command to run when a generated model artifact is absent
- `409` on conflicts: double booking, re-dispensing, editing a signed record
- `403` distinguishes "not your resource" from `401` "not signed in"
- Error bodies never contain stack traces or filesystem paths
