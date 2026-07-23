# Model Card — Hospital Surge Forecaster v1.0

**Task** Predict occupied beds per hospital ward at +24/48/72h.

**Architecture** One HistGradientBoostingRegressor per horizon over features:
lags {1,2,3,7,14}, 7-day rolling mean/std, capacity, day-of-week and
day-of-year sin/cos, one-hot hospital and ward.

**Training data** `data/surge/bed_utilization.csv`: 7,200 daily rows,
5 Dhaka hospitals × 2 ward types × 2 years, with dengue-season and winter
respiratory seasonality plus 41 event shocks (generator seed 42).

**Metrics (60-day holdout)**
| horizon | model MAE | naive persistence MAE |
|---|---|---|
| 24h | 2.75 | 3.96 |
| 48h | 2.92 | 4.05 |
| 72h | 2.99 | 4.13 |

**Limitations** Synthetic utilisation curves; real feeds (admissions,
discharges, referrals) will shift feature importance. Surge alert threshold
(90%) is a policy choice, not learned.
