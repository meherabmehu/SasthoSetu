# -*- coding: utf-8 -*-
"""BanglaMed-AI hospital surge forecasting service.

Implements GET /v1/hospitals/{id}/surge-forecast (platform doc section 13.1):
24/48/72-hour occupied-bed forecasts per ward, produced by the trained
gradient-boosted horizon models using the trailing utilization history.

History source: ``data/surge/bed_utilization.csv`` by default (demo mode).
In production the same feature builder runs against the live bed_status table.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

_ART = Path(__file__).resolve().parent / "artifacts"

def _csv(path):
    """Return path if it exists, else its .gz sibling (fresh clones ship .gz)."""
    import pathlib as _pl
    p = _pl.Path(path)
    return p if p.exists() else p.with_name(p.name + ".gz")

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATA_DIR = Path(os.environ.get("SASTHOSETU_DATA_DIR", _REPO_ROOT / "data"))

_ALERT_RATE = 0.90       # occupancy fraction that raises a surge alert


@lru_cache(maxsize=1)
def _bundle():
    return joblib.load(_ART / "surge_model.joblib")


@lru_cache(maxsize=1)
def _history() -> pd.DataFrame:
    df = pd.read_csv(_csv(_DATA_DIR / "surge" / "bed_utilization.csv"))
    df["date"] = pd.to_datetime(df["date"])
    return df


def _feature_row(hist: pd.DataFrame, bundle: dict,
                 hospital_id: str, ward: str) -> tuple[pd.DataFrame, pd.Series]:
    sub = (hist[(hist.hospital_id == hospital_id) & (hist.ward_type == ward)]
           .sort_values("date"))
    if len(sub) < 15:
        raise ValueError(f"insufficient history for {hospital_id}/{ward}")
    last = sub.iloc[-1]
    nxt = last["date"] + pd.Timedelta(days=1)
    row = {f"lag_{l}": float(sub.iloc[-l]["occupied"]) for l in bundle["lags"]}
    tail7 = sub["occupied"].tail(7)
    row.update({
        "roll7_mean": float(tail7.mean()), "roll7_std": float(tail7.std()),
        "capacity": float(last["capacity"]),
        "dow_sin": float(np.sin(2 * np.pi * nxt.dayofweek / 7)),
        "dow_cos": float(np.cos(2 * np.pi * nxt.dayofweek / 7)),
        "doy_sin": float(np.sin(2 * np.pi * nxt.dayofyear / 366)),
        "doy_cos": float(np.cos(2 * np.pi * nxt.dayofyear / 366)),
    })
    for col in bundle["feature_cols"]:
        if col.startswith("hospital_id_"):
            row[col] = 1.0 if col == f"hospital_id_{hospital_id}" else 0.0
        elif col.startswith("ward_type_"):
            row[col] = 1.0 if col == f"ward_type_{ward}" else 0.0
    X = pd.DataFrame([row])[bundle["feature_cols"]]
    return X, last


def forecast(hospital_id: str, ward_types: list[str] | None = None) -> dict:
    """Forecast occupied beds at +24/+48/+72h for each ward of a hospital."""
    bundle, hist = _bundle(), _history()
    wards = ward_types or sorted(
        hist[hist.hospital_id == hospital_id]["ward_type"].unique())
    if not wards:
        raise ValueError(f"unknown hospital_id {hospital_id!r}")

    out_wards = []
    for ward in wards:
        X, last = _feature_row(hist, bundle, hospital_id, ward)
        cap = int(last["capacity"])
        horizons = []
        for hz in bundle["horizons"]:
            pred = float(bundle["models"][f"h{hz}"].predict(X)[0])
            pred_beds = int(np.clip(round(pred), 0, cap))
            rate = pred_beds / cap
            horizons.append({
                "hours_ahead": hz * 24,
                "predicted_occupied": pred_beds,
                "predicted_available": cap - pred_beds,
                "predicted_occupancy_rate": round(rate, 3),
                "surge_alert": rate >= _ALERT_RATE,
            })
        out_wards.append({
            "ward_type": ward, "capacity": cap,
            "current_occupied": int(last["occupied"]),
            "current_occupancy_rate": float(last["occupancy_rate"]),
            "as_of": last["date"].date().isoformat(),
            "forecast": horizons,
        })

    return {
        "hospital_id": hospital_id,
        "hospital_name": str(
            hist[hist.hospital_id == hospital_id]["hospital_name"].iloc[0]),
        "wards": out_wards,
        "surge_alert_threshold": _ALERT_RATE,
        "model_version": "banglamed-surge-v1.0",
    }


if __name__ == "__main__":
    import json
    print(json.dumps(forecast("H001"), indent=2))
