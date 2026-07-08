# SasthoSetu End-to-End Product Roadmap

This roadmap targets a maintainable healthcare platform, not a hackathon demo.
Every phase must be usable, tested, and documented before the next phase starts.

## Current baseline

Already present:

- FastAPI and SQLAlchemy backend
- User registration and JWT login
- Patient and doctor profiles
- Doctor verification and availability
- Appointment booking, status, cancellation, and rescheduling
- Prescriptions, medical records, patient history, notifications, and files
- Admin statistics and user management
- Safety-first bilingual triage API (`POST /api/v1/triage`)

Known platform-wide gaps:

- No frontend applications
- No database migration history
- Incomplete resource ownership and role authorization
- Limited automated coverage outside triage
- No hospitals, facilities, labs, pharmacies, payments, or teleconsultation
- No FHIR interoperability, offline sync, or production observability

## Phase 0 — Stabilize the backend

Status: In progress

- Central environment configuration and `.env.example`
- Alembic migrations; remove runtime `create_all`
- Standard response and error format
- Role and resource-ownership authorization
- Pagination, filtering, and typed response schemas
- Transaction safety and appointment double-booking protection
- Test database plus unit and API integration tests
- Formatting, linting, and CI

Done when:

- A clean database can be created entirely from migrations.
- Every protected endpoint has role and ownership tests.
- Registration, login, profiles, and health check pass in CI.

## Phase 1 — Complete the patient-to-care journey

- Expand triage symptom ontology and vital-sign safety rules
- Store triage sessions and clinical feedback with audit history
- Match triage specialty to verified doctors
- Search by specialty, location, language, fee, and availability
- Book an appointment directly from a triage result
- Patient and doctor appointment lifecycle with valid state transitions
- Reminder notifications and cancellation policy

Done when:

- A patient can register, create a profile, submit symptoms, receive a safe
  pathway, find a doctor, book a slot, and track the appointment end to end.

## Phase 2 — Patient and doctor web applications

- Patient web app: onboarding, triage, search, booking, records, notifications
- Doctor portal: verification, schedule, queue, patient context, consultation
- Admin portal: verification, users, audit events, and operational statistics
- Responsive Bangla/English UI with accessibility and low-bandwidth budgets
- Generated typed API client and shared design system

Done when:

- Patient, doctor, and admin journeys run in a browser without using Swagger.

## Phase 3 — Consultation and clinical workflow

- Secure consultation session and chat
- Video-provider abstraction and appointment waiting room
- Consultation notes, diagnoses, observations, and follow-up plan
- Structured e-prescription with medicine, dosage, route, frequency, duration
- Allergy and drug-interaction warnings
- Signed prescription QR verification and dispensing state
- Clinical audit trail; records are append-only after signing

Done when:

- A verified doctor can complete a consultation and issue a verifiable
  prescription that appears in the patient's longitudinal history.

## Phase 4 — Hospitals and real-time capacity

- Facility, department, ward, bed, ICU, and emergency-capacity models
- Hospital staff roles and tenant isolation
- Bed update workflow and real-time subscriptions
- Emergency facility search by distance and required capability
- Capacity history and basic demand analytics

Done when:

- Authorized hospital staff can maintain capacity and patients can find an
  appropriate available facility without seeing stale or unauthorized data.

## Phase 5 — Labs and pharmacies

- Lab directory, catalog, pricing, order, sample, and result workflow
- Pharmacy directory, inventory, prescription verification, and dispensing
- Secure diagnostic file delivery
- Patient consent and provider access policies
- Order and result notifications

Done when:

- A prescription or lab order can be fulfilled by a verified provider and the
  result is visible to the patient and authorized clinician.

## Phase 6 — Payments and commercial operations

- Payment-provider abstraction with bKash/Nagad-ready adapters
- Consultation, lab, and pharmacy checkout
- Webhook verification, idempotency, refunds, invoices, and reconciliation
- Provider payout ledger, commissions, subscriptions, and financial reports

Done when:

- All money movements are auditable, idempotent, and reconciled.

## Phase 7 — Interoperability and rural access

- FHIR R4 mapping for Patient, Practitioner, Encounter, Observation,
  MedicationRequest, and DiagnosticReport
- Consent registry and patient identity matching
- FHIR import/export and facility connector
- Offline-capable PWA with encrypted local queue and conflict handling
- SMS notifications and IVR/voice-triage adapter
- Community health worker mode

Done when:

- Core care access survives intermittent connectivity and records can be
  exchanged through tested FHIR resources with explicit patient consent.

## Phase 8 — Intelligence, safety, and governance

- Versioned model-serving interface behind the deterministic safety layer
- Clinician override and outcome feedback workflow
- Dataset lineage, model cards, bias evaluation, and drift monitoring
- Human review queue for low-confidence and high-risk cases
- Population-level analytics using de-identified, minimum-necessary data

Done when:

- Every AI output is versioned, explainable, auditable, clinically governed,
  and safely falls back when confidence or service availability is inadequate.

## Phase 9 — Production readiness

- Containerized deployments and separate environments
- Managed secrets, encryption, backups, restore drills, and disaster recovery
- Structured logs, metrics, tracing, alerting, and status checks
- Rate limiting, abuse controls, security headers, malware scanning, and WAF
- Penetration testing, privacy documentation, retention rules, and incident plan
- Load, accessibility, security, and failover tests

Done when:

- Release, rollback, backup restoration, incident response, and critical user
  journeys have all been rehearsed in a production-like environment.

## Delivery rule

Work in vertical slices. Each slice includes schema/migration, service logic,
authorization, API, UI where applicable, automated tests, and documentation.
No phase is considered complete from models or endpoints alone.
