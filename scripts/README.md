# SasthoSetu Scripts

Utility and automation scripts.

## AI data & model pipeline

The BanglaMed-AI layer (`backend/app/ai/`) needs generated datasets and
trained model artifacts. Regenerate everything with:

```
python ml/prepare_all.py
```

This is deterministic (seed 42) and produces:
- `data/seed/{hospitals,doctors}.json` - reference data for surge forecasting
- `data/triage/symptom_triage_dataset.csv` - 9,000-row triage corpus
- `data/surge/{bed_utilization,surge_events}.csv`
- `data/surveillance/{weekly_surveillance,injected_outbreaks}.csv`
- `backend/app/ai/artifacts/*` - trained triage + surge models

The large CSVs are committed gzipped (`*.csv.gz`); the AI services fall back
to the `.gz` file automatically if the plain CSV isn't present, so a fresh
clone works without regenerating anything. Run `ml/prepare_all.py` only when
you want to retrain on fresh/updated data.

## Database seeding

There is currently no hospital/doctor seed script for the relational
database - `Hospital` is not yet a first-class model (see `docs/
project-roadmap.md` Phase 4). The BanglaMed-AI surge forecaster references
hospitals by code (`H001`-`H005`) directly from `data/seed/hospitals.json`,
independent of the SQL schema, so it works without any DB seeding.
