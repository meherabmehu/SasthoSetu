# -*- coding: utf-8 -*-
"""De-identified AI inference telemetry."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.ai_inference_event import AIInferenceEvent

logger = logging.getLogger("sasthosetu.ai")


def age_band(age: int | None) -> str | None:
    if age is None:
        return None
    if age < 1:
        return "infant"
    if age < 18:
        return "child"
    if age < 40:
        return "18-39"
    if age < 60:
        return "40-59"
    if age < 75:
        return "60-74"
    return "75+"


def record_event(
    db: Session,
    *,
    feature: str,
    model_version: str,
    outcome: str,
    status_code: int = 200,
    latency_ms: float = 0.0,
    fallback_used: bool = False,
    low_confidence: bool = False,
    age_years: int | None = None,
    request_id: str | None = None,
) -> AIInferenceEvent:
    event = AIInferenceEvent(
        feature=feature,
        model_version=model_version,
        outcome=outcome,
        status_code=status_code,
        latency_ms=latency_ms,
        fallback_used=fallback_used,
        low_confidence=low_confidence,
        age_band=age_band(age_years),
        request_id=request_id,
    )
    db.add(event)
    db.commit()

    logger.info(
        "AI inference",
        extra={
            "feature": feature,
            "model_version": model_version,
            "outcome": outcome,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "fallback_used": fallback_used,
            "low_confidence": low_confidence,
        },
    )
    # Alert evaluation is event-driven so it works on a simple Render web
    # service without a separate worker. Delivery is opt-in and throttled.
    try:
        from app.operations.alerts import dispatch_alerts, evaluate_alerts
        from app.operations.release import release_status
        summary = telemetry_summary(db, hours=1)
        dispatch_alerts(evaluate_alerts(summary), release=release_status(db))
    except Exception:
        logger.exception("Operational alert evaluation failed")
    return event


def record_failure(
    db: Session, *, feature: str, model_version: str, status_code: int,
    age_years: int | None = None, request_id: str | None = None,
) -> AIInferenceEvent:
    """Persist a de-identified failure; never store exception text or input."""
    return record_event(
        db, feature=feature, model_version=model_version, outcome="error",
        status_code=status_code, age_years=age_years, request_id=request_id,
    )


def telemetry_summary(db: Session, hours: int = 24) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    base = db.query(AIInferenceEvent).filter(
        AIInferenceEvent.created_at >= cutoff
    )

    total = base.count()
    fallbacks = base.filter(AIInferenceEvent.fallback_used.is_(True)).count()
    low_confidence = base.filter(
        AIInferenceEvent.low_confidence.is_(True)
    ).count()
    errors = base.filter(AIInferenceEvent.status_code >= 400).count()
    avg_latency = db.query(func.avg(AIInferenceEvent.latency_ms)).filter(
        AIInferenceEvent.created_at >= cutoff
    ).scalar() or 0.0

    grouped = (
        db.query(
            AIInferenceEvent.feature,
            func.count(AIInferenceEvent.id),
            func.avg(AIInferenceEvent.latency_ms),
            func.sum(
                case(
                    (AIInferenceEvent.fallback_used.is_(True), 1),
                    else_=0,
                )
            ),
            func.sum(
                case(
                    (AIInferenceEvent.low_confidence.is_(True), 1),
                    else_=0,
                )
            ),
        )
        .filter(AIInferenceEvent.created_at >= cutoff)
        .group_by(AIInferenceEvent.feature)
        .all()
    )

    return {
        "window_hours": hours,
        "total": total,
        "fallbacks": fallbacks,
        "low_confidence": low_confidence,
        "errors": errors,
        "average_latency_ms": round(float(avg_latency), 2),
        "by_feature": [
            {
                "feature": feature,
                "count": int(count),
                "average_latency_ms": round(float(feature_latency or 0), 2),
                "fallbacks": int(fallback_count or 0),
                "low_confidence": int(low_count or 0),
            }
            for feature, count, feature_latency, fallback_count, low_count
            in grouped
        ],
    }
