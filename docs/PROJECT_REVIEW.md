# SasthoSetu implementation review

Historical baseline audit. Follow-up fixes and current demo limitations are
tracked in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md). Statements below
describe the reviewed baseline, not the post-fix working tree.

Reviewed: 2026-11-03 (Asia/Dhaka). Source baseline: `402b09a`.

This is a repository review with local automated checks. It does not establish
the state of the hosted service, external provider accounts, or clinical validity.
No application code was changed for this review.

## Product and architecture

SasthoSetu is a Bangladesh-focused, bilingual healthcare platform. The main
journey is symptom assessment → doctor recommendation → appointment →
consultation → prescription → follow-up records. Hospital capacity, laboratory
orders, pharmacy search, payments and rural access support that journey.

- Backend: FastAPI, SQLAlchemy, Pydantic, Alembic; SQLite for local development,
  PostgreSQL for deployment.
- Frontend: 27 HTML pages with vanilla JavaScript modules, shared styling,
  Bangla/English translations, web manifest and service worker.
- Current generated OpenAPI: 114 API paths, 122 HTTP operations under `/api/`.
- Intelligence: deterministic symptom extraction and escalation rules, trained
  triage and surge models, nine imaging models, statistical surveillance and a
  curated drug interaction knowledge base. Optional LLM symptom extraction.
- Deployment assets: Docker/nginx/Compose and Render, Railway and Vercel files.

## Implemented capabilities

These have substantive code and corresponding tests; presence here does not
mean every edge case or production integration has been independently verified.

| Area | What is implemented | Main evidence |
|---|---|---|
| Accounts | Patient registration, clinician registration pending verification, role-aware sign-in, profile/password changes | `backend/app/modules/auth/`, `users/`; account and registration tests |
| Patient triage | Bangla/Banglish/English extraction, rule escalation, ML endpoint, stored sessions, clinician feedback | `backend/app/ai/`, `modules/triage_sessions/`; triage, model and LLM tests |
| Doctor discovery | Search, recommendation, reviews, availability and booking | `modules/doctors/`, `recommendations/`, `reviews/`, `appointments/` |
| Consultation | Participant-scoped text messages, notes, diagnoses, closure and follow-up | `modules/consultations/`; clinical workflow and chat tests |
| Prescriptions | Structured medication lines, interaction checks, HMAC verification, expiry and dispensing state | `modules/consultations/service.py`; clinical workflow tests |
| Records | Medical history, uploaded files stored in the database, patient records screen | `modules/medical_records/`, `files/`; file upload tests |
| Hospitals | Directory/map, wards, staff access, capacity updates/history, emergency search, demand forecast | `modules/hospitals/`, `ai/surge_service.py` |
| Labs/pharmacies | Provider catalogue, laboratory order/status/result/consent API, pharmacy stock lookup | `modules/providers/`; provider/payment/FHIR tests |
| Payments | Checkout records, local adapter contract, signed callbacks, refund/accounting/reconciliation logic | `modules/payments/`, `payments/gateways.py` |
| Interoperability | FHIR mappings, capability statement and patient bundle | `backend/app/fhir/`, `modules/fhir/` |
| Rural/offline | SMS reply generation, IVR menu logic, CHW batch API, cached pages/reads and write replay | `modules/rural/`, `frontend/service-worker.js`, `frontend/assets/js/api.js` |
| Imaging | Five skin screens, two chest screens, retina and oral screens with committed artifacts and metrics | `backend/app/ai/*_service.py`, `artifacts/`; imaging tests |
| Administration | Doctor/provider verification, capacity, surveillance and reconciliation screens/APIs | `frontend/admin.html`, `modules/admin/` |

## Work remaining, in priority order

### P0 — Patient data access and offline identity

1. **Bind clinician access to a treatment relationship and appropriate consent.**
   `require_self_or_clinician()` in `backend/app/core/security.py` admits any
   `DOCTOR` account without checking verification or a patient relationship.
   Medical record reads and file list/upload routes use this helper. The patient
   prescription listing also permits the doctor role broadly. Authentication
   exists, but it does not establish that the caller treats this patient.
2. **Bind legacy clinical endpoints to the authenticated doctor.**
   `POST /medical-records/{doctor_id}` requires the doctor role, but its service
   accepts the supplied doctor ID without comparing it with the caller. The
   doctor-specific list route likewise lacks that identity comparison. Legacy
   prescription routes also accept doctor IDs without binding them to the caller;
   checking an appointment against a supplied ID does not authenticate that ID. Add
   authorization and regression tests for doctor A using doctor B's ID.
3. **Scope and protect the offline queue.** `api.js` stores one plaintext
   `sasthosetu.queue`; entries contain no owning account, logout leaves the queue
   behind, and replay uses the currently signed-in token. A shared phone can
   therefore replay a previous user's actions under a different account. The
   roadmap's claim of an encrypted queue is not implemented in this file.
4. **Review authenticated service-worker caching.** API responses are cached
   using their request URL without an explicit account namespace. Logout attempts
   to clear data caches, which helps, but account transitions, unfinished writes,
   offline expiry and concurrent tabs need browser tests and clear data-retention
   behavior. LocalStorage read caching is separately account-scoped.

### P1 — External integrations and complete user journeys

5. **Implement actual payment provider clients.** `MobileWalletGateway.initiate`
   and `refund` generate references locally; there is no provider HTTP request.
   Setting an API key only changes `is_sandbox` to false. Credentials alone will
   not make live charges/refunds work. Implement provider-specific authentication,
   checkout, callback validation, transaction verification and refund calls;
   prevent a simulated result from being presented as a live transaction.
6. **Connect SMS/IVR to a telecom service.** The current API returns text/menu
   data. Sending messages, receiving authenticated provider callbacks, phone-call
   sessions and audio delivery still require an external integration.
7. **Complete laboratory/provider web workflows.** There is substantial API
   coverage and a patient results tab, but no dedicated lab operator portal or
   complete patient catalogue/order interface in the current HTML pages.
8. **Clarify consultation scope.** Text consultation is implemented. No audio or
   video calling implementation was found. Add it only if it is part of the
   intended product; avoid describing current messaging as completed video care.
9. **Account recovery and session lifecycle.** Password change exists; no
   forgot-password/reset, email/phone verification, refresh-token flow or token
   revocation mechanism was found. Password changes currently do not revoke
   previously issued JWTs.

### P1 — Verification and delivery

10. **Activate CI.** `.github/workflows/` is absent. The workflow is a template
    at `docs/ci/github-actions-ci.yml`, and its README explicitly says it must be
    copied into the active location. The repository claim that CI is complete is
    therefore premature. Its dependency install also needs the test client.
11. **Declare development/test dependencies.** `httpx2` and `ruff` were missing
    from the local environment; neither is declared in the requirements files.
    Current Starlette's TestClient requires `httpx2`. Make fresh-install testing
    reproducible rather than relying on manually installed packages.
    Also rebuild/version-align `tb_model.joblib`: loading it under pinned
    scikit-learn 1.5.2 warns that its estimators were saved with 1.6.1. The test
    suite passes despite this warning, so its artifact checks do not fully cover
    the compatibility claim in the AI report.
12. **Exercise real PostgreSQL and concurrency.** Existing PostgreSQL tests
    compile DDL without connecting to a server. Add an actual database job and
    concurrent appointment/dispensing/payment tests. Booking uses a separate
    initial read and locked re-read and should be tested with two sessions;
    SQLite cannot verify PostgreSQL row-lock behavior.
13. **Run browser end-to-end checks.** Verify patient, doctor and admin journeys,
    bilingual rendering, mobile layouts, accessibility, account switching and
    offline replay in a browser. Python HTML/source assertions do not establish
    browser behavior. This review did not perform browser QA.
14. **Strengthen operational checks.** `/health` returns a constant healthy
    response without database/model readiness checks. Add readiness monitoring,
    backup/restore drills, realistic load/failover checks and shared rate limiting
    when scaling beyond one process. Review trust of `X-Forwarded-For` at the
    deployment boundary.

### P1/P2 — Data quality and model evaluation

15. **Distinguish real observations from simulated operational data.** Facility
    names/coordinates come from real sources, but missing emergency/capacity
    fields have inferred/demo values. These cannot establish live available beds.
    Surge training is generated. The surveillance runtime loads generated weekly
    data even though real dengue data has been downloaded. Live feeds and verified
    update timestamps remain necessary.
16. **Collect independent clinician-labelled Bangla complaints.** Triage combines
    generated examples with Bangla notes reconstructed from real ED presentations;
    its labels are reassigned by project rules. Reported emergency recall measures
    this test corpus, not prospective clinical performance in Bangladesh.
17. **Check leakage and external validity of imaging metrics.** For example,
    HAM10000 training uses shuffled image indices and PAD uses class-stratified
    image indices, without grouping by patient/lesion in those split functions.
    Audit repeated subjects/lesions and duplicates, rebuild grouped splits where
    possible, then evaluate on an independent local cohort. This is a leakage
    risk, not proof that every published score is invalid.
18. **Expand skin-tone evidence and review referral mappings.** The existing
    audit documents sparse darker-skin data. Thresholds and disease-to-referral
    mappings require clinician review. Dataset licensing and permitted commercial
    use must also be resolved for the chosen deployment (HAM10000 is documented
    as noncommercial in the repository).

### P2 — Documentation consistency

19. Refresh the roadmap and README using verified results. Test totals disagree
    between documents (281, 336 and 359); current OpenAPI exposes 122 operations,
    while the README claims 116 endpoints. `docs/REAL_DATA.md` still describes all
    corpora as generated despite later real imaging/facility work. Preserve the
    distinction between implementation, simulation, integration and validation.

## Validation

- `python -m unittest discover -s tests`: **359 tests run, OK, 19 skipped**
  (340 passed), about 168 seconds. Dataset-dependent imaging checks are among
  the skipped coverage; this is not a full image-dataset evaluation.
- `python -m ruff check backend ml scripts tools`: **all checks passed**
  using Ruff 0.17.3 (the inactive CI template pins 0.8.4).
- Migration upgrade, metadata comparison and downgrade tests passed as part of
  the full suite. PostgreSQL DDL compilation passed; no live PostgreSQL server
  was exercised.
- The initial test run was impeded by missing `httpx2`, causing cascading
  import/metadata failures. After installing `httpx2` and `ruff` into `.venv`,
  the full suite passed. Those initial failures were not 24 independent defects.
- The completed suite emitted scikit-learn `InconsistentVersionWarning` for
  `tb_model.joblib` (saved 1.6.1, runtime 1.5.2), confirmed by loading the artifact
  separately. Resolve this before relying on reproducible inference.
- Raw test output: `review-tests.log` in the repository root (ignored by Git).
- No hosted endpoints, external accounts, provider transactions, production
  database, browser workflows or clinical cohorts were tested.

## Recommended delivery order

1. Close patient authorization and offline account isolation gaps.
2. Establish reproducible tests and active CI, including PostgreSQL and browser QA.
3. Complete provider integrations and unfinished laboratory/account journeys.
4. Replace simulated operational feeds, evaluate models independently and run a
   clinically supervised pilot with appropriate approvals.
5. Verify production operations and update all completion claims.
