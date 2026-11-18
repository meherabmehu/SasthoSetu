# Data acquisition audit — 18 November 2026

This audit records what was actually downloaded, what was safely integrated,
and what remains unavailable without an agreement. A public URL alone is not
treated as permission to train or deploy a clinical model.

## Acquired and integrated

| Need | Source and licence | Result | Product use |
|---|---|---|---|
| Bangladesh dengue trend | [Mendeley daily dengue estimates](https://data.mendeley.com/datasets/z5mvwrfgsz/1), CC BY 4.0 | 8,768 division-day rows, 2022-01-01 to 2024-12-31 | Default historical API source: `bangladesh_dengue_estimates_2022_2024`. It is not live, official, district-level, or suitable for real-time alerts. |
| Bangladesh skin images | [SkinDiseaseBD v3](https://data.mendeley.com/datasets/9ggd3shdr7/3), CC BY-NC 4.0 | 197 original images are present separately from augmented archives | Kept out of the served model until patient/image split metadata and clinician validation are available. The augmented images are excluded to prevent leakage. |

The dengue raw archive SHA-256 and the canonical table provenance are stored in
`data/real/bd_dengue_daily_2022_2024.provenance.json`. Raw images and archives
remain ignored by Git.

## Downloaded but excluded from training

| Source | Why excluded |
|---|---|
| [Bangla Healthcare Severity Dataset](https://data.mendeley.com/datasets/37z8kgx79m/1), CC BY 4.0 | Its released CSV contains question-mark replacement for most text, so it is not usable as Bangla free text. It also has four manually assigned classes that do not map safely to SasthoSetu's five clinician urgency levels. The aggregate integrity report is `backend/app/ai/artifacts/bangla_severity_external_audit.json`. |
| Existing public image mirrors without complete lineage | Kept research/demo-only per their model cards; no claim of independent clinical validation. |
| [SkinDisNet v2](https://data.mendeley.com/datasets/yj3md44hxg/2) | The public archive transfer is not yet complete and has not passed container validation. Its images are therefore not extracted, inspected, trained on, or served. |

## Located but requires a data-use agreement or permission

| Need | Source | Required before use |
|---|---|---|
| Diverse dermatology external test set | [DDI](https://ddi-dataset.github.io/) | Individual registration and research agreement; research-only/no-derivative terms apply. |
| Bangladesh dermatology set | [DermaBD-7](https://mshahinur.github.io/DermaBD-7/) | Request the authors' non-commercial research permission and obtain the files. |
| Daily per-ward occupancy | A Bangladeshi hospital admission/bed system | A hospital data-sharing agreement and de-identified daily ward records. Public DGHS data is not sufficient for this target. |
| Live surveillance | DGHS/IEDCR feed or data-sharing agreement | A documented machine-readable, current feed and operational escalation owner. |
| Live payments, SMS, IVR | A Bangladesh provider account | Credentials, contract, compliance review, and production callback verification. This project remains sandbox/demo as requested. |

## Training decision

No new clinical model was trained from the new sources in this audit. That is a
deliberate quality gate: the available Bangla severity labels/text are unusable,
and the 197 original SkinDiseaseBD images have no patient-level grouping. A
model trained by mixing its 1,612 augmented images into train/test would report
misleading performance. The next defensible training run needs clinician review
and a patient/image-group split; it should be promoted only after a held-out,
Bangladeshi evaluation passes predeclared safety thresholds.

The in-product collection path is ready for that partner work: only a verified
doctor can submit a triage review, and the retraining script joins reviewed
sessions to verified doctors. General user feedback is deliberately excluded
from model training.
