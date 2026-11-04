# Implementation status — 2026-11-04

Scope: safe demo/sandbox, as selected by the project owner. Payments move no
real money, SMS is not delivered, and real email is disabled by default.

## Completed in this change

| Review item | Result |
|---|---|
| Patient data access | Verified treating doctor plus explicit patient consent required for shared history, files, triage and FHIR. Patients manage grants/revocations in Account. Active relationships include confirmed, in-progress and completed appointments. |
| Doctor impersonation | Legacy clinical and appointment routes bind the supplied doctor ID to the authenticated verified doctor. Consultation triage links must refer to the same patient. |
| Offline privacy | AES-GCM encrypted, expiring, account/tab-scoped reads and writes; old plaintext storage removed; logout clears private storage; responses from a previous session are rejected; queue replay is serialized and checks identity. The service worker no longer stores API responses. |
| Payments | Always clearly labelled demo, even if gateway credentials exist. Patient ownership and idempotency reuse are checked. Payer-only success/failure simulator, callback replay protection and locked refunds. No provider HTTP calls or real money movements. |
| Rural channels | Sandbox responses identify themselves; unverified submitted phone numbers no longer attach anonymous SMS assessments to real accounts. Telecom delivery remains outside this scope. |
| Laboratory journey | Patient catalogue/booking page, result-sharing controls and demo checkout; operator catalogue/order/status/report workspace; admin assignment of an operator by email. Unrelated consultation/report attachments are rejected. |
| Recovery and sessions | Single-use hashed expiring reset/verification tokens, rotating refresh API, password-change/reset/logout session revocation, account recovery page and verification control. Demo mail goes to an admin-only in-memory outbox, not a mailbox. |
| Delivery | GitHub Actions workflow, declared development dependencies, browser job and actual PostgreSQL migration/concurrency job. The workflow runs on pushes and pull requests to main; remote results are available in the repository Actions tab. |
| Operations | `/health` liveness, `/ready` database/schema/required-model checks, explicit proxy trust, optional shared database rate limits, disposable PostgreSQL backup/restore drill and local concurrency smoke tools. |
| Model compatibility | Runtime rejects incompatible scikit-learn artifacts. TB was genuinely retrained under the pinned 1.5.2 runtime and restored. Seven imaging models have recorded validation calibration and grouped holdout results. |
| Evaluation split tooling | Acquired/refreshed seven image collections (42,580 source images). Patient/lesion and duplicate/perceptual components remain disjoint. Exclusions, source-file hashes, split manifests, per-image predictions and uncertainty intervals accompany the models. See MODEL_RETRAINING_2026-11-04.md. |
| Data honesty | Demo labels on capacity, forecasts, surveillance and payment surfaces; API provenance flags distinguish simulated data from verified live feeds. |

CI model generation uses the committed source data with `--skip-download`.
The data generators and trainers still run; external dataset acquisition is
kept separate so remote source availability does not control test reproducibility.

## Run locally

Install development tools with `python -m pip install -r requirements-dev.txt`.
Configure `backend/.env`, then apply both new migrations before starting the app:

```powershell
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
```

New revisions: `20261103_0009` (care consent and account security) and
`20261103_0010` (optional shared rate-limit counters). Existing users begin at
session version zero. Existing doctor access does not imply a consent grant;
patients must explicitly grant access in Account.

The user's existing database and deployment were not modified by this work.
Migrations were exercised on isolated SQLite and PostgreSQL databases.

For a completely separate browser demo:

```powershell
.\.venv\Scripts\python.exe tools/review_server.py
```

It creates a new database under `.tmp` and listens on `127.0.0.1:8765`.
Fixture-only users are `patient@qa.example`, `doctor@qa.example`,
`admin@qa.example`, `operator@qa.example`, `other@qa.example`, all with password
`BrowserDemo123!`. These accounts are never created in the user's app database.

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe tools/browser_smoke.py
.\.venv\Scripts\python.exe tools/load_smoke.py
```

`QA_PORT` / `QA_BASE_URL` allow another local port; `QA_CHROMIUM_PATH` can select
an installed Chromium executable. The browser test checks a 390px viewport,
desktop rendering and language switching, but is not a full accessibility audit.

## Configuration

- `ACCOUNT_EMAIL_MODE=demo`: stores temporary reset/verification links in the
  admin-only demo outbox. No email is sent. This is the development default;
  staging/production defaults to disabled. Never use the demo outbox for real
  patient accounts. Messages disappear on process restart and expire in 30 minutes.
- `ACCOUNT_EMAIL_MODE=smtp`: optional future mail delivery using `SMTP_HOST`,
  `SMTP_PORT` (587), `SMTP_FROM`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and
  `PUBLIC_APP_URL`. STARTTLS is required. This session did not test or send SMTP.
- `RATE_LIMIT_BACKEND=memory`: default for one demo process.
- `RATE_LIMIT_BACKEND=database`: atomic counters shared by instances on the same
  database. Counter identifiers are HMACs of client addresses and old windows
  are removed. Database unavailability fails closed with 503.
- `TRUSTED_PROXY_CIDRS`: empty by default. Only trusted peers' forwarded client
  addresses are considered. Configure the reverse proxy itself to strip incoming
  client-supplied forwarding headers. Otherwise rely on the actual peer address.
- Payment API keys do not enable live payments. All current gateways and refunds
  are local demo simulations; replacing this requires real provider integrations.

## Validation performed

- Imaging retraining verification (2026-11-04): **393 tests, OK, 7 skipped**
  (386 passed), including the downloaded-image checks. Six skipped checks need
  an opt-in PostgreSQL URL; the seventh covers intentionally absent artifacts.
  Ruff and staged diff checks passed. All 11 committed models load under the
  pinned scikit-learn runtime; the expanded deployment checks passed separately.
  The seven active imaging model/label hashes match their frozen holdout reports.
- CI smoke seeding now uses the same backend-anchored SQLite URL as migrations
  and the API. Fresh local migrations plus seeding completed successfully in a
  disposable database. GitHub results are recorded in Actions after publication.
  Logs: `.tmp/retraining-full-suite-final.log`, `.tmp/deployment-artifact-tests.log`
  and `.tmp/ci-seed-check.log` (local and gitignored).

- Security regression checks cover patient grants/revocation, unrelated and
  unverified doctors, forged doctor IDs, FHIR, token replay/expiry, password and
  logout revocation, demo mail access, payment ownership, simulation, readiness
  and shared counters.
- Real PostgreSQL: upgrade, metadata comparison, downgrade/rebuild, concurrent
  same-slot booking, single dispensing, duplicate callbacks, refund limits and
  shared counters. All six checks passed in a private disposable schema.
- A real `pg_dump`/`pg_restore` drill restored and verified a random sentinel in
  its own disposable schema. This is not a backup of production data.
- Browser: patient login, grant/revoke, lab booking, operator reporting, patient
  results, demo email verification, encrypted queue, offline logout/account
  switching, absence of API data in worker caches, doctor/admin pages, mobile
  overflow and language toggle passed against an isolated fixture server.
- Local request smoke: 40 requests, eight concurrent clients, zero errors.
  This does not establish production throughput or failover behavior.
- Previous suite, before imaging retraining: **386 tests, OK, 25 skipped** (361 passed). The six opt-in
  PostgreSQL tests were then exercised separately and all passed; other skips
  included missing image datasets and the absent-artifact branch. Ruff passed. Browser checks also covered
  demo lab payment completion and a failed login identity lookup. Local output
  is in `review-tests.log`, `review-postgres.log` and `.tmp/browser-smoke-completion.log`.
- Final publishing review also verifies `Cache-Control: no-store` on private API
  responses, rejects mixed checkout targets, and rejects missing/NaN grouping IDs.
- A tracked-source snapshot rebuilt the datasets and triage/surge models without
  downloading data (229 seconds locally). Its standalone AI checks then ran 34
  tests successfully (one skipped). The degraded-mode test group now owns its
  temporary SQLite database instead of depending on earlier tests' setup.

## Still requires data, infrastructure or an external party

1. Independent clinician-labelled Bangla cases, local skin-tone cohorts,
   clinician review of referral mappings and prospective clinical validation.
2. Verified hospital capacity and real surveillance feeds; these remain simulated
   in the selected demo scope. Downloading a real file alone does not make the
   current operational feed live.
3. Source patient identities for the retina/oral mirrors and some TB/MSID cases
   remain unavailable. Duplicate grouping does not establish patient independence;
   independent source cohorts and verified image-level provenance are needed.
4. Production licensing clearance, external penetration/accessibility audits,
   realistic infrastructure failover/load tests and actual backup/restore drills
   on the chosen production deployment.
5. Live gateway and telecom integrations were explicitly deferred by the owner.
   Text consultation is implemented; audio/video calling remains unimplemented
   and was not established as a requirement for this demo.
