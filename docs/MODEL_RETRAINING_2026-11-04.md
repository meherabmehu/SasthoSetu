# Imaging retraining — 2026-11-04

Seven public image collections were acquired or refreshed and trained locally under the pinned Python 3.12 / scikit-learn 1.5.2 runtime. This release is for demo/research only. It does not establish diagnostic accuracy in Bangladesh or authorize clinical deployment.

## Frozen evaluation

Source patient IDs (PAD, MSLD and recognizable TB filenames), HAM lesion IDs, exact decoded-pixel duplicates and 64-bit perceptual hashes (Hamming distance ≤4) form connected components before splitting. Unreadable/blank images, exact duplicates and every conflicting-label pixel duplicate are excluded. Seed-42 stratified group folds separate training, validation and test. HAM uses ten folds, MSID/MSLD five and the remaining datasets seven; one fold each is reserved for validation and test. Near-duplicate matching is heuristic, not proof of independence.

Classifier selection uses validation macro-F1 across logistic regression, histogram boosting and balanced extra trees (400 trees). The highest observed threshold meeting 90% validation positive recall is frozen before test evaluation, with a 1e-12 downward numerical margin to keep parallel tree summation roundoff from losing a boundary case. HAM includes malignant/precancerous labels; PAD positives are BCC/SCC/MEL; retina positives are severe/proliferative; other positives are TB, monkeypox or oral carcinoma respectively. Weighted concern scores retain the serving contract.

Research release gate: disjoint components, validation recall ≥90%, nonzero validation specificity, at least ten positive holdout images and holdout recall ≥80%. Test results participate only in this acceptance gate, not classifier or threshold tuning. This is not a clinical safety standard.

| Dataset | Source / excluded | Train / validation / test | Test recall (95% component CI) | Specificity | Macro-F1 | Research gate |
|---|---:|---:|---:|---:|---:|---|
| skin | 10015 / 2 | 8029 / 1014 / 970 | 88.6% (83.6%–93.3%) | 63.1% | 0.433 | pass |
| mpox | 770 / 4 | 457 / 156 / 153 | 83.6% (72.9%–92.9%) | 67.3% | 0.515 | pass |
| msld | 755 / 1 | 455 / 135 / 164 | 96.6% (90.2%–100.0%) | 18.9% | 0.385 | pass |
| tb | 15990 / 83 | 11413 / 2237 / 2257 | 89.3% (86.4%–91.9%) | 81.7% | 0.855 | pass |
| pad | 2298 / 29 | 1615 / 336 / 318 | 87.2% (81.5%–92.7%) | 35.0% | 0.341 | pass |
| dr | 2750 / 126 | 1872 / 362 / 390 | 93.1% (85.9%–98.5%) | 53.3% | 0.432 | pass |
| oral | 10002 / 0 | 7144 / 1431 / 1427 | 90.3% (88.1%–92.5%) | 93.1% | 0.919 | pass |

Intervals resample test components 1,000 times. They measure sampling uncertainty within these collections, not transportability. All partitions, hashes, per-image predictions, confusion counts and validation metrics accompany the model artifacts.

## Provenance and limitations

| Collection | Extracted images | Source licence | Patient identity |
|---|---:|---|---|
| [HAM10000](https://doi.org/10.7910/DVN/DBW86T) | 10015 | CC BY-NC 4.0 | Some or all patient IDs are unavailable; duplicate separation is not patient-level validation. |
| [MSID v6](https://data.mendeley.com/datasets/r9bfpnvyxr/6) | 770 | CC BY 4.0 | Some or all patient IDs are unavailable; duplicate separation is not patient-level validation. |
| [MSLD v2 originals](https://github.com/ShamsNafisaAli/Monkeypox-Skin-Lesion-Dataset-v2) | 755 | CC BY 4.0 (authors' badge) | source patient groups |
| [TB/pneumonia/COVID/normal mirror](https://huggingface.co/datasets/DevVoyageR007/classify_Pneumonia_Tuberculosis_and_Normal__Non_Xray_chest_Xray_images) | 15990 | Mirror declares no licence; underlying lineage not fully verified | Some or all patient IDs are unavailable; duplicate separation is not patient-level validation. |
| [PAD-UFES-20 v1](https://data.mendeley.com/datasets/zr7vgbcyr2/1) | 2298 | CC BY 4.0 | source patient groups |
| [Retinopathy 256px mirror](https://huggingface.co/datasets/Rami/Diabetic_Retinopathy_Preprocessed_Dataset_256x256) | 2750 | Mirror declares no licence | Some or all patient IDs are unavailable; duplicate separation is not patient-level validation. |
| [Oral carcinoma/normal mirror](https://huggingface.co/datasets/Alwaly/Oral_Cancer-cancer) | 10002 | Mirror declares no licence | Some or all patient IDs are unavailable; duplicate separation is not patient-level validation. |

Downloaded archive/shard SHA-256 values, immutable Hugging Face revisions and file sizes are recorded in [dataset_sources.json](../data/real/imaging/dataset_sources.json). Public availability does not establish reuse rights. Images and source archives remain local and gitignored. HAM is noncommercial; unclear mirror licences require independent clearance.

MSLD uses the 755 originals once (fold1), with filename patient IDs; augmented images and repeated fold directories are not new cases. TB is stored as lossless 128px PNG after the exact serving resize; a regression test verifies unchanged runtime features. Its original archive is retained. Retina/oral mirrors lack patient IDs and may include unknown source transformations or augmentation; their results cannot be called patient-independent. MSID is web-collected, not a Bangladesh clinical cohort.

Cross-collection exact decoded-pixel matches: mpox/msld: 10. Near matches and shared patients can still exist. Separate skin/rash screens are not proven independent ensemble evidence.

The previous scores in AI_REPORT.md used different splits and are historical. No numerical improvement over those scores is claimed. The improvement here is compatible retraining, better validation separation, source traceability and measured uncertainty. Inspect specificity alongside recall: high referral rates can place substantial burden on clinicians.

The [skin-tone audit](model_cards/skin_tone_audit.md) uses only PAD's held-out test images. Independent consented local cases, darker-skin cohorts, clinician-reviewed referral mappings, prospective external validation and licensing clearance remain necessary before real use.

## Reproduction

```powershell
python -m pip install -r requirements-ml.txt
$env:SASTHOSETU_ARTIFACT_DIR = '.tmp/imaging-candidates'
# Acquire originals with ml/fetch_{skin,mpox,msld,dr,oral,pad}_data.py individually.
python ml/fetch_tb_data.py --compact
# Run ml/train_{skin,tb,pad,mpox,msld,dr,oral}_model.py individually.
python ml/evaluate_imaging.py skin tb pad mpox msld dr oral --artifacts .tmp/imaging-candidates
python ml/audit_skin_tones.py --artifacts .tmp/imaging-candidates
python ml/report_imaging.py --artifacts .tmp/imaging-candidates
python ml/promote_imaging.py --source .tmp/imaging-candidates
```

Allow over 15 GB for archives plus extraction space. Range downloads resume completed chunks; feature caches are invalidated when ordered metadata, file attributes or feature code changes. Only evaluated artifacts passing the research gate are copied into the serving directory. Restart running application processes to reload their cached model bundles.
