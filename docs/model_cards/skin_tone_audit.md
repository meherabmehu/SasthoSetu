# Skin-tone audit — held-out smartphone photographs

Only PAD's frozen test partition is included. Patient IDs and duplicate components are disjoint from training and validation. The model and referral threshold were fixed before this audit.

রেফার হার and malignant recall are reported separately. Positive labels are BCC, SCC and MEL; the referral score also weights precancerous ACK. These are retrospective research results, not clinical validation or evidence of performance on Bangladeshi patients.

| Fitzpatrick type | Test images | Malignant images | Referral rate | Malignant recall | Specificity |
|---|---:|---:|---:|---:|---:|
| I — সবচেয়ে ফর্সা | 37 | 30 | 83.8% | 83.3% | 14.3% |
| II — ফর্সা | 108 | 81 | 86.1% | 91.4% | 29.6% |
| III — গমবর্ণ | 40 | 25 | 67.5% | 80.0% | 53.3% |
| IV — বাদামি | 14 | 5 | 71.4% | 80.0% | 33.3% |
| V — গাঢ় বাদামি | 0 | 0 | unmeasured | unmeasured | unmeasured |
| VI — কালো | 0 | 0 | unmeasured | unmeasured | unmeasured |

119 test images lack a Fitzpatrick label and are omitted from tone comparisons.

Zero positive cases means recall is unmeasured. Small groups cannot establish parity; the companion JSON reports 95% component-bootstrap intervals (1,000 repetitions), which remain unreliable for very small groups. Fitzpatrick type is a limited proxy, not ethnicity.

Independent consented Bangladeshi cohorts, especially darker skin types, and clinician review are still required. No fairness claim follows from these results.

Source: [PAD-UFES-20, CC BY 4.0](https://data.mendeley.com/datasets/zr7vgbcyr2/1).

Reproduce: `python ml/audit_skin_tones.py` after `python ml/evaluate_imaging.py pad --artifacts backend/app/ai/artifacts`.
