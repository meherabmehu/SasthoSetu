# 🩺 SasthoSetu — সাস্থ্যসেতু

**AI-assisted health platform for Bangladesh.** Bilingual symptom triage, doctor
matching and booking, teleconsultation, cryptographically verifiable
prescriptions, live hospital bed capacity, labs and pharmacies, payments, FHIR
R4 interoperability, and access channels for people without a smartphone.

---

## Why this exists

Bangladesh has roughly 3 doctors per 10,000 people against a WHO minimum of 10.
Patients travel hours for advice that a safe triage answer could have replaced,
prescriptions are filled incorrectly at unregulated counters, and no unified
record follows a patient between facilities.

SasthoSetu addresses those three gaps directly, and is built so that the people
least served by existing apps — rural, offline, non-literate — are first-class
users rather than an afterthought.

---

## What works today

| Capability | Detail |
|---|---|
| **Bilingual triage** | Bangla, Banglish, English and code-switched input. Deterministic red-flag layer plus a calibrated ML classifier |
| **Clinical safety** | 10 hard-coded red-flag rules that can only escalate. Machine learning never lowers a severity a rule has raised |
| **Doctor matching** | Ranked by soonest availability, filtered to BMDC-verified doctors |
| **Consultations** | Notes, diagnosis, secure messaging; records become append-only once signed |
| **Prescriptions** | Multi-item, HMAC-signed, single-use dispensing, forgery and expiry detection |
| **Drug safety** | 152 Bangladeshi brand aliases over 73 generics, 81 curated interaction pairs, duplicate-therapy detection |
| **Hospital capacity** | Per-ward bed tracking, append-only history, emergency routing by availability then distance |
| **Surge forecasting** | 24/48/72-hour per-ward bed demand, holdout MAE ≈ 2.9 beds |
| **Surveillance** | District × disease anomaly detection for outbreak early warning |
| **Labs & pharmacies** | Ordering, results under patient consent, generic-matched stock search |
| **Payments** | bKash, Nagad, Rocket, SSLCommerz behind one interface; idempotent, signature-verified, reconciled |
| **Interoperability** | FHIR R4 resources and a per-patient `$everything` bundle |
| **Rural access** | SMS triage, IVR menus, offline CHW batch submission |
| **Web apps** | Patient, doctor and admin surfaces; installable PWA that works offline |

**149 automated tests.** Every red-flag rule is asserted in four phrasings —
natural Bangla, romanised Banglish, English, and English paraphrase.

---

## Quick start

### Docker (recommended)

```bash
cp .env.example .env
# set SECRET_KEY and POSTGRES_PASSWORD
docker compose up --build
```

Open http://localhost:8080. The first start builds the datasets and trains the
models, which takes a minute or two.

### Local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt uvicorn

python ml/prepare_all.py                       # datasets + models (~90s)

cd backend
cp .env.example .env                           # set DATABASE_URL and SECRET_KEY
alembic upgrade head
cd .. && python scripts/seed_database.py       # facilities, doctors, demo logins

cd backend && uvicorn app.main:app --reload
```

Serve the frontend from any static server:

```bash
cd frontend && python -m http.server 5500
```

### Demo accounts

| Role | Email | Password |
|---|---|---|
| Admin | `admin@sasthosetu.gov.bd` | `Admin@12345` |
| Doctor | `doctor@sasthosetu.gov.bd` | `Doctor@12345` |
| Patient | `patient@sasthosetu.gov.bd` | `Patient@12345` |

---

## Architecture

```
frontend/            Patient, doctor and admin web apps (vanilla ES modules, PWA)
backend/
  app/
    ai/              Lexicon, extraction, safety rules, model serving
    core/            Config, database, security, middleware
    fhir/            FHIR R4 resource mapping
    models/          SQLAlchemy models
    modules/         Feature modules (routes + service per domain)
    payments/        Gateway abstraction and adapters
    schemas/         Pydantic request and response models
  alembic/           Migrations
  tests/             149 tests
ml/                  Dataset generators, training, retraining
scripts/             Database seeding
docker/              Entrypoint and nginx configuration
docs/                Roadmap, API notes, model cards, CI workflow
```

### Triage pipeline

```
raw note (bn / banglish / en / mixed)
   ↓  entity extraction  — lexicon of 57 symptoms, negation, duration, age
   ↓  red-flag check     — 10 deterministic rules
   ↓  ML classification  — TF-IDF word + char n-grams + structured features
   ↓  safety override    — escalate only, never downgrade
   ↓  care pathway, specialty, confidence, bilingual disclaimer
```

Safety rules are deliberately rule-based rather than learned. They must be
auditable and must never regress silently between model versions.

---

## The AI layer

| Model | Task | Performance |
|---|---|---|
| Triage classifier | 5-level severity from free text | macro-F1 **0.840**, emergency recall **0.975**, no errors spanning ≥3 bands |
| Surge forecaster | 24/48/72h bed demand per ward | MAE **≈2.9 beds**, beats naive persistence at every horizon |
| Surveillance detector | District × disease outbreak anomalies | EWMA + robust z-score, 25/25 injected outbreaks detected |
| Drug interaction screen | Brand-aware pair checking | 81 curated pairs, 152 brand aliases |

Full limitations are documented in `docs/model_cards/`. The corpora are
synthetic but principled, generated from the same lexicon the runtime uses.
**Clinical validation is required before real-world deployment**, and the model
cards say so explicitly.

### Learning loop

Clinician overrides feed retraining:

```bash
python ml/retrain_from_feedback.py --dry-run   # inspect first
python ml/retrain_from_feedback.py
```

Corrections enter only the training split. A retrained model is promoted only
if macro-F1 holds within tolerance **and** emergency recall does not fall at
all; otherwise the previous corpus and model are restored.

---

## Rural access

| Channel | For | Endpoint |
|---|---|---|
| SMS | Feature phones | `POST /api/v1/rural/sms/triage` |
| IVR | Non-literate callers | `GET /api/v1/rural/ivr/menu`, `POST /api/v1/rural/ivr/select` |
| CHW batch | Offline home visits | `POST /api/v1/rural/chw/batch` |
| Offline PWA | Intermittent data | Service worker with a queued write replay |

SMS replies are composed against the 160-character limit — Bangla in UCS-2 gets
70 per segment, and a reply that fragments may not arrive intact.

---

## Testing

```bash
cd backend
APP_ENV=test DATABASE_URL=sqlite:///./test.db \
  SECRET_KEY=test-secret-key-at-least-32-characters-long \
  python -m unittest discover -s tests -v
```

```bash
ruff check backend ml scripts tools
```

CI (`docs/ci/`) lints, builds the datasets, trains the models, runs migrations,
runs the suite, then boots a real server and asserts that Bangla chest pain with
breathlessness returns `EMERGENCY` over HTTP.

---

## Security

- bcrypt password hashing; JWT bearer sessions
- Role and resource-ownership checks on every protected endpoint
- HMAC-signed prescriptions; any edit invalidates the signature
- Per-client rate limiting, security headers, request correlation IDs
- Errors never leak stack traces or filesystem paths
- Patient consent gates lab results reaching a clinician
- Containers run unprivileged

---

## API

Interactive documentation at `/docs` once running. 99 endpoints across triage,
appointments, consultations, prescriptions, hospitals, labs, pharmacies,
payments, FHIR, rural access and administration.

See `docs/API.md` for the AI and clinical surface, and `docs/BANGLAMED_AI.md`
for how each model works.

---

## Roadmap

`docs/project-roadmap.md` tracks phase status and what remains.

---

## Licence

MIT
