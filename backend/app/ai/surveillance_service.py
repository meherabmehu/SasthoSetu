# -*- coding: utf-8 -*-
"""BanglaMed-AI population health surveillance service.

Implements GET /v1/population/surveillance (platform doc section 13.1):
district x disease weekly trends with statistical anomaly detection.

Detector: EWMA baseline + robust z-score on the most recent weeks. A week is
anomalous when observed cases exceed baseline by >= ``z_threshold`` standard
deviations (minimum-sigma floored to avoid tiny-count false alarms). Simple,
explainable, and validated against the injected ground-truth outbreaks in
``data/surveillance/injected_outbreaks.csv``.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd


def _csv(path):
    """Return path if it exists, else its .gz sibling (fresh clones ship .gz)."""
    import pathlib as _pl
    p = _pl.Path(path)
    return p if p.exists() else p.with_name(p.name + ".gz")

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATA_DIR = Path(os.environ.get("SASTHOSETU_DATA_DIR", _REPO_ROOT / "data"))


@lru_cache(maxsize=1)
def _weekly() -> pd.DataFrame:
    df = pd.read_csv(_csv(_DATA_DIR / "surveillance" / "weekly_surveillance.csv"))
    df["week_ending"] = pd.to_datetime(df["week_ending"])
    return df


def _detect(series: pd.Series, z_threshold: float, span: int = 8
            ) -> tuple[pd.Series, pd.Series]:
    baseline = series.ewm(span=span, adjust=False).mean().shift(1)
    resid = series - baseline
    sigma = resid.rolling(12, min_periods=4).std().shift(0)
    sigma = sigma.clip(lower=np.maximum(1.5, baseline.pow(0.5).fillna(1.5)))
    z = (resid / sigma).fillna(0.0)
    return z, baseline


def surveillance(district: str | None = None, disease: str | None = None,
                 weeks: int = 26, z_threshold: float = 2.5) -> dict:
    """Return recent trends + anomaly alerts, optionally filtered."""
    df = _weekly()
    if district:
        df = df[df.district.str.lower() == district.lower()]
    if disease:
        df = df[df.disease.str.lower() == disease.lower()]
    if df.empty:
        raise ValueError("no surveillance data for the given filters")

    cutoff = df["week_ending"].max() - pd.Timedelta(weeks=weeks)
    series_out, alerts = [], []
    for (dist, dis), grp in df.groupby(["district", "disease"]):
        grp = grp.sort_values("week_ending").reset_index(drop=True)
        z, baseline = _detect(grp["cases"], z_threshold)
        grp = grp.assign(z=z.round(2), baseline=baseline.round(1))
        recent = grp[grp.week_ending > cutoff]
        pts = [{"week_ending": r.week_ending.date().isoformat(),
                "cases": int(r.cases),
                "expected": None if pd.isna(r.baseline) else float(r.baseline),
                "z_score": float(r.z),
                "anomaly": bool(r.z >= z_threshold)}
               for r in recent.itertuples()]
        series_out.append({"district": dist, "disease": dis, "points": pts})
        for p in pts:
            if p["anomaly"]:
                alerts.append({"district": dist, "disease": dis, **p})

    alerts.sort(key=lambda a: (a["week_ending"], -a["z_score"]), reverse=True)
    return {
        "window_weeks": weeks,
        "z_threshold": z_threshold,
        "series": series_out,
        "active_alerts": alerts[:50],
        "alert_count": len(alerts),
        "detector": "EWMA(span=8) + robust z-score",
        "model_version": "banglamed-surveillance-v1.0",
    }


def detector_validation(z_threshold: float = 2.5) -> dict:
    """Recall of the detector against the injected ground-truth outbreaks."""
    truth = pd.read_csv(_DATA_DIR / "surveillance" / "injected_outbreaks.csv")
    hits = 0
    for row in truth.itertuples():
        res = surveillance(district=row.district, disease=row.disease,
                           weeks=200, z_threshold=z_threshold)
        alert_weeks = {a["week_ending"] for a in res["active_alerts"]}
        window = pd.date_range(row.start_week, row.end_week, freq="W-SUN")
        if any(w.date().isoformat() in alert_weeks for w in window):
            hits += 1
    return {"injected_outbreaks": len(truth), "detected": hits,
            "recall": round(hits / len(truth), 3), "z_threshold": z_threshold}


if __name__ == "__main__":
    import json
    res = surveillance(district="Dhaka", disease="dengue", weeks=12)
    print(json.dumps({k: res[k] for k in ("alert_count", "active_alerts")},
                     indent=2)[:600])
    print(json.dumps(detector_validation(), indent=2))
