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


@lru_cache(maxsize=1)
def _bangladesh_dengue_daily() -> pd.DataFrame:
    """Return the documented historical estimate series, not a live feed."""
    path = _DATA_DIR / "real" / "bd_dengue_daily_2022_2024.csv"
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"], format="%d-%m-%y")
    df["estimated_cases"] = pd.to_numeric(df["estimated_cases"], errors="raise")
    return df


def _detect(series: pd.Series, z_threshold: float, span: int = 8
            ) -> tuple[pd.Series, pd.Series]:
    baseline = series.ewm(span=span, adjust=False).mean().shift(1)
    resid = series - baseline
    sigma = resid.rolling(12, min_periods=4).std().shift(0)
    sigma = sigma.clip(lower=np.maximum(1.5, baseline.pow(0.5).fillna(1.5)))
    z = (resid / sigma).fillna(0.0)
    return z, baseline


def _historical_dengue(district: str | None, disease: str | None,
                       weeks: int, z_threshold: float) -> dict:
    """Serve a clearly labelled historical dengue-estimate analysis."""
    if disease and disease.lower() != "dengue":
        raise ValueError("this historical source contains dengue estimates only")
    df = _bangladesh_dengue_daily()
    if district:
        df = df[df.division.str.lower() == district.lower()]
    if df.empty:
        raise ValueError("no historical dengue data for the given division")

    cutoff = df["date"].max() - pd.Timedelta(weeks=weeks)
    series_out, alerts = [], []
    for division, group in df.groupby("division"):
        weekly = (group.set_index("date")["estimated_cases"].sort_index()
                  .resample("W-SUN").sum().reset_index())
        z, baseline = _detect(weekly["estimated_cases"], z_threshold)
        weekly = weekly.assign(z=z.round(2), baseline=baseline.round(2))
        recent = weekly[weekly.date > cutoff]
        points = [{
            "week_ending": row.date.date().isoformat(),
            "cases": round(float(row.estimated_cases), 2),
            "expected": None if pd.isna(row.baseline) else float(row.baseline),
            "z_score": float(row.z),
            "anomaly": bool(row.z >= z_threshold),
        } for row in recent.itertuples()]
        series_out.append({"district": division, "disease": "dengue", "points": points})
        for point in points:
            if point["anomaly"]:
                alerts.append({"district": division, "disease": "dengue", **point})
    alerts.sort(key=lambda alert: (alert["week_ending"], -alert["z_score"]), reverse=True)
    return {
        "data_source": "bangladesh_dengue_estimates_2022_2024",
        "is_live": False,
        "historical": True,
        "geographic_level": "division",
        "coverage": {"start": "2022-01-01", "end": "2024-12-31"},
        "measure": "Estimated dengue affected people (fractional values retained)",
        "not_for_real_time_alerting": True,
        "window_weeks": weeks,
        "z_threshold": z_threshold,
        "series": series_out,
        "active_alerts": alerts[:50],
        "alert_count": len(alerts),
        "detector": "EWMA(span=8) + robust z-score; retrospective analysis",
        "model_version": "banglamed-surveillance-v1.1",
    }


def surveillance(district: str | None = None, disease: str | None = None,
                 weeks: int = 26, z_threshold: float = 2.5,
                 source: str = "bangladesh_dengue_estimates_2022_2024") -> dict:
    """Return historical real data by default; synthetic data is opt-in only."""
    if source == "bangladesh_dengue_estimates_2022_2024":
        return _historical_dengue(district, disease, weeks, z_threshold)
    if source != "synthetic_demo":
        raise ValueError("unknown surveillance source")
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
        "data_source": "synthetic_demo", "is_live": False,
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
