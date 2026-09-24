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

---

## `imaging/dermnet_labels.csv` — 15,557 skin photographs, 23 conditions

**Source:** [Muzmmillcoste/dermnet](https://huggingface.co/datasets/Muzmmillcoste/dermnet)
on Hugging Face, derived from DermNet.

**Licence:** MIT.

**Contents:** filename, condition, Bangla name, referral band, split. The
images themselves are extracted to `imaging/dermnet/` and not committed.

**Why this matters more than HAM10000 here.** HAM10000 covers pigmented
lesions only. The conditions a Bangladeshi clinic actually sees — ringworm and
other fungal infection (1,300 images), eczema (1,235), nail fungus (1,040),
scabies, bacterial infection, acne — are absent from it entirely. These are
also ordinary photographs rather than dermatoscope images, which is much closer
to what a phone camera produces.

**Caveats.** Web-sourced, so image quality varies and the labels are the site's
own categories rather than biopsy-confirmed diagnoses. Predominantly
light-skinned. The mapping from the 23 conditions to three referral bands is a
clinical judgement made in `ml/fetch_medical_datasets.py` and is the first
thing a doctor reviewing this project should check.

---

## `imaging/chest_xray_labels.csv` — 5,856 chest films

**Source:** [mmenendezg/pneumonia_x_ray](https://huggingface.co/datasets/mmenendezg/pneumonia_x_ray),
originally Kermany, Zhang & Goldbaum, Mendeley Data (2018).

**Licence:** CC BY 4.0.

**Contents:** filename, finding (normal or pneumonia), Bangla name, split.

Pneumonia is among the leading causes of death in children under five in
Bangladesh. Upazila health complexes can take a film; a radiologist to read it
is often a district away.

**Caveats.** Paediatric films from a single hospital in Guangzhou. Adult films
and different equipment will look different, and a photograph of a film taken
on a phone is not the same as the film itself.

---

## What is still generated

| Corpus | Why it is still synthetic |
|---|---|
| `data/triage/` | No public dataset carries a clinician urgency label against **Bangla** free text. Must be collected with a clinical partner. |
| `data/surge/` | DGHS publishes bed occupancy monthly and per facility; the forecaster needs daily and per ward. Requires a hospital data-sharing agreement. |
| `data/drugs/` | Real brand-to-generic data exists (DGDA, 25,000+ entries) but the official export needs a browser session or a written request. |

See `docs/REAL_DATA.md` for the full assessment.

---

## `imaging/mpox_labels.csv` — 770 viral-rash photographs, 4 classes

**Source:** [Monkeypox Skin Images Dataset (MSID)](https://data.mendeley.com/datasets/r9bfpnvyxr/6),
Department of Computer Science and Engineering, Islamic University, Kushtia,
Bangladesh. DOI 10.17632/r9bfpnvyxr.6.

**Licence:** CC BY 4.0. Cite the dataset and its contributors.

**Contents:** 279 monkeypox, 107 chickenpox, 91 measles and 293 normal-skin
photographs collected from internet health sources.

**Why it is here.** The viral exanthems that circulate in Bangladesh are
absent from DermNet and HAM10000 entirely; without this screen a rash
photograph had no class it could land in that meant "monkeypox". The
dataset is small (770 images) and web-sourced, so its screen is exactly
that — a screen that raises a referral, never a diagnosis.

---

## `imaging/tb_labels.csv` — 15,990 chest films, 4 classes

**Source:** a [Hugging Face collection](https://huggingface.co/datasets/
DevVoyageR007/classify_Pneumonia_Tuberculosis_and_Normal__Non_Xray_chest_
Xray_images) aggregating several long-public chest-film sets. The
tuberculosis films trace back to the US National Library of Medicine's
Montgomery County and Shenzhen collections and the Belarus/NIAID sets; the
pneumonia and COVID films to the RSNA and other public corpora.

**Licence:** the aggregation repo declares none. The underlying US NLM
collections are US Government public domain; the Belarus set is CC BY 4.0.
Only the derived label CSV is committed - the films stay out of the
repository and are re-fetchable.

**Contents:** 4,197 tuberculosis, 4,273 pneumonia, 2,031 COVID-19 and
5,489 normal films. The source's "unknown" folder (1,818 films) is
dropped: a class whose provenance cannot be stated cannot be explained to
a clinician.

**Why it is here.** Tuberculosis is among the top infectious causes of
death in Bangladesh, and the pneumonia screen we already served had no
class that could mean it.

---

## `imaging/pad_labels.csv` — 2,298 smartphone photographs, 6 diagnoses

**Source:** [PAD-UFES-20](https://data.mendeley.com/datasets/zr7vgbcyr2/1),
smartphone photographs collected in Brazil with clinical context (age,
Fitzpatrick skin type, body region, symptoms).

**Licence:** CC BY 4.0.

**Contents:** 845 basal cell carcinoma, 730 actinic keratosis, 244
melanocytic nevus, 235 seborrheic keratosis, 192 squamous cell carcinoma
and 52 melanoma photographs.

**Why it is here.** Every other lesion dataset we serve is dermatoscopic
or a textbook atlas; this one is ordinary phone photographs under
whatever light the room had, which is exactly what our users submit. The
paper: Pacheco et al., "PAD-UFES-20: A skin lesion dataset composed of
single images captured by smartphones", 2020.

---

## `imaging/msld_labels.csv` — 755 verified viral-rash photographs, 6 classes

**Source:** [MSLD v2.0](https://github.com/ShamsNafisaAli/Monkeypox-Skin-Lesion-Dataset-v2)
by Shams Nafisa Ali et al., also on [Kaggle](https://www.kaggle.com/datasets/joydippaul/mpox-skin-lesion-dataset-version-20-msld-v20)
and Google Drive. Class labels verified by a dermatologist.

**Licence:** CC BY 4.0 (the authors' license badge). Cite the dataset
paper: Ali et al., "MSLD: Moneypox Skin Lesion Dataset", 2022, and its
version 2.0 release notes.

**Contents:** 284 monkeypox, 161 hand-foot-mouth disease, 114 healthy, 75
chickenpox, 66 cowpox and 55 measles photographs - one fold of the
published five-fold layout, because every image appears in all five folds.

**Why it is here.** Cowpox and hand-foot-mouth disease appear in no other
dataset we serve, and the whole collection is dermatologist-verified -
a stronger review than the web-sourced MSID set.

---

## `imaging/dr_labels.csv` — 2,750 retina photographs, 5 grades

**Source:** a [Hugging Face mirror](https://huggingface.co/datasets/
Rami/Diabetic_Retinopathy_Preprocessed_Dataset_256x256) of a Kaggle
diabetic retinopathy collection, itself built from the public EyePACS-style
screening corpora and resized to 256x256.

**Licence:** the mirror declares none. The underlying Kaggle competition
data (APTOS/EyePACS-derived) is released for research use; only the
derived label CSV is committed and the photographs stay out of the
repository, re-fetchable from the mirror.

**Contents:** 1,000 healthy, 900 moderate, 370 mild, 290 proliferative and
190 severe retinopathy photographs.

**Why it is here.** Diabetes prevalence among Bangladeshi adults has
passed ten percent and retinopathy is a leading cause of preventable
blindness; a fundus camera in an upazila vision centre is realistic, an
ophthalmologist is not.

---

## `imaging/oral_labels.csv` — 10,002 mouth photographs, 2 classes

**Source:** a [Hugging Face mirror](https://huggingface.co/datasets/
Alwaly/Oral_Cancer-cancer) of a Kaggle oral-cancer collection of clinical
photographs - 5,001 oral squamous cell carcinoma and 5,001 normal.

**Licence:** the mirror declares none. Only the derived label CSV is
committed; the photographs stay out of the repository and are re-fetchable.

**Contents:** balanced two-class clinical photographs of the inside of the
mouth.

**Why it is here.** Oral cancer is among the commonest cancers in
Bangladesh, driven by betel-quid and tobacco chewing, and presents late. A
health worker with a phone torch can take this photograph; the screen
answers the screening question.
