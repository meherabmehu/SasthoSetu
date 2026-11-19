"""Optional Sentry setup; disabled without a DSN."""
from __future__ import annotations

from app.core.config import settings


def initialize_sentry() -> bool:
    if not settings.sentry_dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.app_env,
            release=settings.app_version,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            send_default_pii=False,
            integrations=[FastApiIntegration()],
        )
        return True
    except Exception:
        # Monitoring must never prevent clinical safety rules from starting.
        return False
