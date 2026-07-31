# SasthoSetu Scripts

Utility and automation scripts.

## AI data & model pipeline

The BanglaMed-AI layer (`backend/app/ai/`) needs generated datasets and
trained model artifacts. Build everything with:

```
python ml/prepare_all.py
```

This is deterministic (seed 42) and takes roughly 1-2 minutes on CPU. It
produces:

- `data/seed/{hospitals,doctors}.json` - reference data for surge forecasting
- `data/drugs/{bd_brand_aliases,drug_interactions}.csv` - drug knowledge base
- `data/triage/symptom_triage_dataset.csv` - 9,000-row triage corpus
- `data/surge/{bed_utilization,surge_events}.csv`
- `data/surveillance/{weekly_surveillance,injected_outbreaks}.csv`
- `backend/app/ai/artifacts/*` - trained triage + surge models and metrics

What is and is not committed:

- **Committed** - the small, human-reviewable reference data:
  `data/seed/*.json` and `data/drugs/*.csv`. These are curated content that
  deserves review in a diff, and keeping them tracked means drug-interaction
  screening works straight from a clone.
- **Not committed** - the large generated corpora (`data/triage`,
  `data/surge`, `data/surveillance`) and the trained model artifacts
  (`backend/app/ai/artifacts/`). These are rebuilt from the scripts above,
  which are the source of truth.

A fresh clone must therefore run `ml/prepare_all.py` (or let CI run it) before
the ML endpoints will serve. Until then those endpoints return `503` naming the
command to run, rather than failing obscurely.

Individual steps can be run on their own, in this order:

```
python ml/generate_seed.py
python ml/generate_drug_kb.py
python ml/generate_triage_dataset.py
python ml/generate_bed_logs.py
python ml/generate_surveillance.py
python ml/train_triage_model.py
python ml/train_surge_model.py
```

## Retraining from clinician feedback

`POST /api/v1/ai/feedback` records clinician corrections in the `ai_feedback`
table. To fold them back into the training corpus:

```
python ml/retrain_from_feedback.py
```

The script refuses to replace the live artifact if the retrained model scores
worse than the current one, so feedback can never silently degrade triage.

## Database seeding

Populate a database with the reference hospitals, doctors and demo accounts:

```
python scripts/seed_database.py
```

Run `alembic upgrade head` first. The script is idempotent - re-running it
updates existing rows rather than creating duplicates.
