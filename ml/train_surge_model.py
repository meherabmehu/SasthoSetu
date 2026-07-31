# -*- coding: utf-8 -*-
"""Train the Predictive Surge Model (48/72-hour bed-demand forecast).

Approach: gradient-boosted trees on lag/rolling/calendar features — trains in
seconds, serves without deep-learning dependencies inside FastAPI, and is the
documented hackathon-speed stand-in for the LSTM described in the platform
document (the LSTM is listed as the post-hackathon upgrade in the model card).

Three horizon models: occupied beds at t+1, t+2, t+3 days.
Time-based holdout: final 60 days.

Artifacts -> backend/app/ai/artifacts/
    surge_model.joblib   {models: {8p: h1,h2,h3}, feature_cols, categories}
    surge_metrics.json
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor


def _csv(path):
    """Return path if it exists, else its .gz sibling (fresh clones ship .gz)."""
    import pathlib as _pl
    p = _pl.Path(path)
    return p if p.exists() else p.with_name(p.name + ".gz")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "surge" / "bed_utilization.csv"
ART = ROOT / "backend" / "app" / "ai" / "artifacts"

LAGS = [1, 2, 3, 7, 14]
HORIZONS = [1, 2, 3]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["hospital_id", "ward_type", "date"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    g = df.groupby(["hospital_id", "ward_type"], group_keys=False)
    for lag in LAGS:
        df[f"lag_{lag}"] = g["occupied"].shift(lag)
    df["roll7_mean"] = g["occupied"].apply(
        lambda s: s.shift(1).rolling(7).mean())
    df["roll7_std"] = g["occupied"].apply(
        lambda s: s.shift(1).rolling(7).std())
    dow = df["date"].dt.dayofweek
    doy = df["date"].dt.dayofyear
    df["dow_sin"] = np.sin(2 * np.pi * dow / 7)
    df["dow_cos"] = np.cos(2 * np.pi * dow / 7)
    df["doy_sin"] = np.sin(2 * np.pi * doy / 366)
    df["doy_cos"] = np.cos(2 * np.pi * doy / 366)
    for hz in HORIZONS:
        df[f"y_h{hz}"] = g["occupied"].shift(-hz)
    df = pd.get_dummies(df, columns=["hospital_id", "ward_type"], dtype=float)
    return df


def main() -> None:
    raw = pd.read_csv(_csv(DATA))
    df = build_features(raw)
    feat_cols = ([f"lag_{l}" for l in LAGS]
                 + ["roll7_mean", "roll7_std", "capacity",
                    "dow_sin", "dow_cos", "doy_sin", "doy_cos"]
                 + [c for c in df.columns
                    if c.startswith(("hospital_id_", "ward_type_"))])

    cutoff = df["date"].max() - pd.Timedelta(days=60)
    metrics, models = {}, {}
    for hz in HORIZONS:
        d = df.dropna(subset=feat_cols + [f"y_h{hz}"])
        tr, te = d[d.date <= cutoff], d[d.date > cutoff]
        m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.06,
                                          random_state=42)
        m.fit(tr[feat_cols], tr[f"y_h{hz}"])
        pred = m.predict(te[feat_cols])
        mae = float(np.mean(np.abs(pred - te[f"y_h{hz}"])))
        mape = float(np.mean(np.abs(pred - te[f"y_h{hz}"])
                             / np.clip(te[f"y_h{hz}"], 1, None))) * 100
        naive = float(np.mean(np.abs(te["lag_1"] - te[f"y_h{hz}"])))
        metrics[f"h{hz}"] = {"test_mae_beds": round(mae, 2),
                             "test_mape_pct": round(mape, 2),
                             "naive_persistence_mae": round(naive, 2)}
        models[f"h{hz}"] = m
        print(f"t+{hz}d: MAE={mae:.2f} beds  MAPE={mape:.1f}%  "
              f"(naive persistence MAE={naive:.2f})")

    ART.mkdir(parents=True, exist_ok=True)
    joblib.dump({"models": models, "feature_cols": feat_cols,
                 "lags": LAGS, "horizons": HORIZONS},
                ART / "surge_model.joblib", compress=3)
    (ART / "surge_metrics.json").write_text(json.dumps(
        {"holdout_days": 60, **metrics}, indent=2))
    print(f"artifacts -> {ART}")


if __name__ == "__main__":
    main()
