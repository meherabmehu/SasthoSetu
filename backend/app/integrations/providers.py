"""Provider readiness without exposing credentials or contacting providers.

This module is deliberately status-only. It gives operators an honest picture
of what must be configured before a live integration can be enabled, while
keeping the demo unable to send an SMS or move money by accident.
"""
from __future__ import annotations

from app.core.config import settings
from app.payments.gateways import registered_gateway_status


def messaging_provider_status() -> dict:
    configured = bool(settings.sms_provider_api_url and settings.sms_provider_api_key)
    return {
        "channel": "sms_ivr",
        "provider": settings.sms_provider_name or "not_selected",
        "configured": configured,
        "live_enabled": False,
        "mode": "sandbox_only",
        "next_step": (
            "Implement and security-review a provider adapter plus delivery receipts"
            if configured
            else "Set SMS_PROVIDER_NAME, SMS_PROVIDER_API_URL and SMS_PROVIDER_API_KEY"
        ),
    }


def provider_readiness() -> dict:
    """Return metadata only; never return a secret, URL query or token."""
    return {
        "payments": registered_gateway_status(),
        "messaging": messaging_provider_status(),
        "live_integrations_enabled": False,
        "notice": "All external delivery and payment paths remain sandbox-only.",
    }
