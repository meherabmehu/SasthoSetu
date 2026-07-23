# Model Card — Outbreak Anomaly Detector v1.0

**Task** Flag anomalous weekly disease counts per district × disease.

**Method** EWMA(span=8) expected baseline; residual scaled by 12-week rolling
std with a floor of max(1.5, sqrt(baseline)) to suppress small-count noise;
alert at z ≥ 2.5. Fully deterministic and explainable — every alert returns
observed, expected, and z-score.

**Validation** 25/25 injected ground-truth outbreaks detected
(`data/surveillance/injected_outbreaks.csv`), recall 1.0 at the default
threshold on the generated 12-district × 8-disease × 157-week corpus.

**Limitations** Reporting delays, weekend effects, and under-reporting in
real DGHS data are not modelled; threshold tuning against historical false
alarm tolerance is required before operational use.
