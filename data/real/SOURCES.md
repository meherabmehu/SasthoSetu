# Real data in this directory

These files are derived from public sources. Unlike everything under
`data/triage/`, `data/surge/` and `data/surveillance/`, the rows here are real
observations rather than generated ones.

Rebuild any of them with:

```bash
python ml/fetch_real_data.py
python ml/fetch_real_data.py --only nhamcs
```

The raw downloads land in `_cache/` and are not committed — they are large and
re-fetchable. The derived CSVs are committed so the project works from a clone
without network access.

---

## `nhamcs_ed_triage.csv` — 9,446 emergency department visits

**Source:** [National Hospital Ambulatory Medical Care Survey 2022](https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHAMCS/),
US National Center for Health Statistics, Centers for Disease Control and
Prevention.

**Licence:** US Government public domain work. No restriction on use.
Attribution to NCHS is expected in publications.

**Contents:** one row per ED visit — age, sex, vital signs, up to three coded
reasons for the visit rendered as their documented English wording, and the
triage immediacy the nurse assigned.

**Note on the label.** The survey codes immediacy 1 (seen immediately) through
5 (2–24 hours). Our own scale runs the other way: 5 is the emergency. The
`severity_level` column has been reversed to match ours.

**Note on what this can and cannot be used for.** The two scales answer
different questions. NHAMCS asks *how quickly must this person be seen, now
that they are in an emergency department*. SasthoSetu asks *what should this
person do, from home* — which includes "nothing, rest and watch it". Everyone
in NHAMCS has already decided to attend hospital, so the population is
filtered. Training directly on these labels teaches the model that shortness of
breath is routine, because in an ED waiting room it usually is.

It is therefore used as **vocabulary**, not as labels: see
`ml/extend_lexicon_from_real.py`, which measures how much of the real complaint
vocabulary the symptom lexicon recognises.

---

## `bd_health_facilities.csv` — 6,000+ Bangladeshi health facilities

**Source:** [Bangladesh Healthsites](https://data.humdata.org/dataset/bangladesh-healthsites),
Global Healthsites Mapping Project, published via the Humanitarian Data
Exchange. Underlying data from OpenStreetMap contributors.

**Licence:** Open Database License (ODbL). **Attribution to OpenStreetMap
contributors is required** wherever this data is displayed, and derived
databases must be shared under the same terms.

**Contents:** name, facility type, latitude, longitude, operator, and where
recorded, bed count, emergency availability and speciality.

**Known gaps.** Bed counts are recorded for only 2 of 1,556 hospitals, and
emergency availability for 92. `ml/build_facility_seed.py` therefore assigns
capacity by facility tier, which is an assumption and is marked as such in that
script. Live bed occupancy must come from each hospital's own system.

---

## `bd_dengue_monthly.csv`, `bd_dengue_by_division.csv`

**Source:** [DENV-Data-Analysis](https://github.com/awnonbhowmik/DENV-Data-Analysis),
compiled from Directorate General of Health Services (DGHS) daily press
releases and the Institute of Epidemiology, Disease Control and Research
(IEDCR).

**Licence:** research dataset accompanying a published paper; cite the
repository. The underlying counts are DGHS government publications.

**Contents:** 288 months of national dengue infections (2001–2024) and 48
division-year rows with cases and deaths.

---

## `bangla_disease_symptoms.csv` — 85 diseases, 172 Bangla symptoms

**Source:** [A Structured Bangla Dataset of Disease-Symptom Associations](https://data.mendeley.com/datasets/rjgjh8hgrt/5),
Khulna University of Engineering & Technology.

**Licence:** CC BY 4.0. Cite:

> R. Zannat, A. Al Shafi and A. Muntakim, "Bridging the Gap in Bangla
> Healthcare: Machine Learning Based Disease Prediction Using a
> Symptoms-Disease Dataset," 2025 International Conference on Electrical,
> Computer and Communication Engineering (ECCE), Chittagong, Bangladesh, 2025.

**Contents:** disease-to-symptom associations in Bangla. Structured pairs, not
free text, and with no urgency label — useful for widening the symptom
vocabulary, not for training the triage classifier.

---

## What is still generated

| Corpus | Why it is still synthetic |
|---|---|
| `data/triage/` | No public dataset carries a clinician urgency label against **Bangla** free text. Must be collected with a clinical partner. |
| `data/surge/` | DGHS publishes bed occupancy monthly and per facility; the forecaster needs daily and per ward. Requires a hospital data-sharing agreement. |
| `data/drugs/` | Real brand-to-generic data exists (DGDA, 25,000+ entries) but the official export needs a browser session or a written request. |

See `docs/REAL_DATA.md` for the full assessment.
