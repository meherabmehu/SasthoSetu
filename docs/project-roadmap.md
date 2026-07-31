# SasthoSetu Product Roadmap

This roadmap targets a maintainable healthcare platform, not a demo. Every
phase must be usable, tested and documented before the next begins.

Status is recorded against what actually executes and is covered by tests, not
against what has been written. An earlier revision of this document listed the
AI layer and a frontend as present when neither ran; that is the failure mode
this file now guards against.

---

## Current state

**149 automated tests passing. 99 API endpoints. Lint clean.**

| Phase | Status |
|---|---|
| 0 — Stabilise the backend | **Complete** |
| 1 — Patient-to-care journey | **Complete** |
| 2 — Web applications | **Complete** |
| 3 — Consultation and clinical workflow | **Complete** |
| 4 — Hospitals and real-time capacity | **Complete** |
| 5 — Labs and pharmacies | **Complete** |
| 6 — Payments and commercial operations | **Complete** |
| 7 — Interoperability and rural access | **Complete** |
| 8 — Intelligence, safety and governance | **Complete** |
| 9 — Production readiness | **Substantially complete** — see remaining work |

---

## Phase 0 — Stabilise the backend ✅

- Central environment configuration with validation
- Alembic migrations; a clean database builds entirely from them
- Role and resource-ownership authorisation on protected endpoints
- Pagination and typed response schemas
- Appointment double-booking protection with a locked slot re-read
- Test database plus unit and API integration tests
- Linting and CI

## Phase 1 — Patient-to-care journey ✅

- Triage over a 57-symptom bilingual ontology with vital-sign rules
- Triage sessions stored with clinician review and audit history
- Specialty matched to verified doctors, ranked by soonest availability
- Search by specialty, fee and availability
- Booking directly from a triage result
- Appointment lifecycle with valid state transitions and notifications

## Phase 2 — Web applications ✅

- Patient app: onboarding, triage, search, booking, records, prescriptions
- Doctor portal: queue, consultation workspace, prescribing, schedule
- Admin portal: verification, capacity, surveillance, settlement
- Responsive Bangla/English UI, WCAG AA contrast, keyboard reachable,
  reduced-motion honoured
- Installable PWA with offline support

## Phase 3 — Consultation and clinical workflow ✅

- Consultation sessions with participant-scoped secure messaging
- Notes, diagnoses, investigations and follow-up plans
- Structured e-prescriptions with medicine, strength, frequency, duration,
  route and instructions
- Allergy and drug-interaction warnings screened before signing
- HMAC-signed prescriptions with single-use dispensing
- Records append-only after signing

## Phase 4 — Hospitals and real-time capacity ✅

- Facility, ward, bed and staff models with tenant isolation
- Bed update workflow with append-only history
- Emergency facility search ranked by availability then distance
- Capacity history and 72-hour demand forecasting

## Phase 5 — Labs and pharmacies ✅

- Lab directory, catalogue, ordering, sample and result workflow
- Pharmacy directory and generic-matched inventory search
- Patient consent gating clinician access to results
- Order and result notifications

## Phase 6 — Payments and commercial operations ✅

- Gateway abstraction with bKash, Nagad, Rocket and SSLCommerz adapters
- Checkout for consultations and lab orders
- Signature-verified webhooks, idempotency, refunds and reconciliation
- Commission splitting and provider payout accounting

## Phase 7 — Interoperability and rural access ✅

- FHIR R4 mapping: Patient, Practitioner, Organization, Encounter,
  Observation, MedicationRequest, DiagnosticReport
- CapabilityStatement and per-patient `$everything` bundle
- Offline-capable PWA with an encrypted local queue
- SMS triage and IVR voice menus
- Community health worker batch mode

## Phase 8 — Intelligence, safety and governance ✅

- Versioned model serving behind a deterministic safety layer
- Clinician override and outcome feedback workflow
- Dataset lineage, model cards and documented limitations
- Retraining with a no-regression promotion gate, stricter on emergency recall
- Population analytics over de-identified data

## Phase 9 — Production readiness

**Done**

- Containerised deployment running unprivileged, with health checks
- Compose stack with PostgreSQL and nginx
- Managed secrets through environment configuration
- Structured logging with request correlation IDs
- Rate limiting, security headers, no stack traces or paths in responses
- CI covering lint, migrations, tests and a live smoke test

**Remaining before a live clinical deployment**

These are deliberately listed rather than quietly omitted. None are code
defects; each needs infrastructure, an external party, or real-world data.

| Item | Why it is not done here |
|---|---|
| Clinical validation of BanglaMed-AI | Requires a registered clinical advisory board and real patient data under ethics approval. The model cards state this precondition explicitly |
| Real BMDC, DGHS and gateway credentials | Requires signed institutional agreements. Adapters run in clearly labelled sandbox mode until then |
| Backup and restore drills | Requires the target production infrastructure |
| Penetration test and security audit | Requires an external assessor |
| Load and failover testing | Requires a production-like environment |
| Distributed rate limiting | In-process limiting is correct for one instance and a conservative floor behind several; a shared store is needed once multi-node |
| Real training corpora | The current corpora are synthetic but principled. Replacing them with de-identified clinical text is the single largest quality improvement available |

---

## Delivery rule

Work in vertical slices. Each slice includes schema and migration, service
logic, authorisation, API, UI where applicable, automated tests and
documentation. No phase is complete on models and endpoints alone — and no
phase is marked complete here unless its tests run green.
