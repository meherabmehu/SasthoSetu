"""Opt-in webhook alerts for aggregate, de-identified operational signals."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from threading import RLock

from app.core.config import settings

logger = logging.getLogger("sasthosetu.operations")
_DELIVERY_LOCK = RLock()
_last_delivery_at: datetime | None = None
_COOLDOWN = timedelta(minutes=5)


def evaluate_alerts(summary: dict) -> list[dict]:
    """Turn aggregate telemetry into small, actionable alerts."""
    total = int(summary.get("total") or 0)
    errors = int(summary.get("errors") or 0)
    alerts = []
    if total and errors / total >= settings.alert_error_rate_threshold:
        alerts.append({"kind": "error_rate", "severity": "critical", "message": "AI error rate exceeded its threshold."})
    if float(summary.get("average_latency_ms") or 0) >= settings.alert_latency_ms_threshold:
        alerts.append({"kind": "latency", "severity": "warning", "message": "AI average latency exceeded its threshold."})
    return alerts


def webhook_status() -> dict:
    parsed = urlparse(settings.alert_webhook_url)
    valid_url = parsed.scheme == "https" and bool(parsed.netloc)
    return {
        "configured": bool(settings.alert_webhook_url),
        "enabled": settings.alert_webhook_enabled and valid_url,
        "safe_url": valid_url,
        "delivery": "webhook" if settings.alert_webhook_enabled and valid_url else "disabled",
    }


def dispatch_alerts(alerts: list[dict], *, release: dict) -> dict:
    """Send no patient text, images, identifiers or secrets to the webhook."""
    status = webhook_status()
    if not alerts or not status["enabled"]:
        return {**status, "sent": 0}
    global _last_delivery_at
    with _DELIVERY_LOCK:
        now = datetime.now(timezone.utc)
        if _last_delivery_at and now - _last_delivery_at < _COOLDOWN:
            return {**status, "sent": 0, "cooldown": True}
        _last_delivery_at = now
    payload = json.dumps({"service": "SasthoSetu", "alerts": alerts, "release": release}).encode("utf-8")
    request = urllib.request.Request(
        settings.alert_webhook_url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "SasthoSetu-Operations/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if 200 <= response.status < 300:
                return {**status, "sent": len(alerts)}
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        logger.warning("Operational alert delivery failed: %s", error)
    return {**status, "sent": 0, "delivery_error": True}
