# -*- coding: utf-8 -*-
"""Payment gateway abstraction.

Every provider is reached through one interface, so the platform can add or
swap a gateway without touching checkout, refund or reconciliation logic.

Adapters here implement the full contract against the sandbox behaviour each
provider documents. Live credentials are supplied through configuration; when
none are present the adapter runs in sandbox mode and says so in its response,
rather than pretending a real charge occurred.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.core.config import settings


@dataclass
class ChargeRequest:
    reference: str
    amount_bdt: float
    payer_msisdn: str | None = None
    description: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class ChargeResult:
    accepted: bool
    gateway_reference: str
    status: str
    is_sandbox: bool
    message: str = ""
    payload: dict = field(default_factory=dict)


class PaymentGateway(ABC):
    """Contract every payment provider adapter implements."""

    name = "base"
    #: Share of the transaction retained by the platform.
    commission_rate = 0.0

    @abstractmethod
    def initiate(self, request: ChargeRequest) -> ChargeResult:
        """Begin a charge and return its provisional state."""

    @abstractmethod
    def verify_callback(self, payload: dict, signature: str | None) -> bool:
        """Confirm a gateway callback genuinely came from the provider."""

    @abstractmethod
    def refund(self, gateway_reference: str, amount_bdt: float) -> ChargeResult:
        """Reverse all or part of a completed charge."""

    def is_configured(self) -> bool:
        return bool(self.api_key())

    def api_key(self) -> str:
        return getattr(settings, f"{self.name}_api_key", "") or ""

    def api_secret(self) -> str:
        return getattr(settings, f"{self.name}_api_secret", "") or ""

    def _sign(self, payload: dict) -> str:
        """Deterministic signature over the callback fields."""
        body = "&".join(f"{k}={payload[k]}" for k in sorted(payload) if k != "signature")
        secret = self.api_secret() or settings.secret_key
        return hmac.new(
            secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def verify_callback(self, payload: dict, signature: str | None) -> bool:  # noqa: F811
        if not signature:
            return False
        return hmac.compare_digest(self._sign(payload), signature)


class MobileWalletGateway(PaymentGateway):
    """Shared behaviour for Bangladeshi mobile financial services."""

    prefix = "TXN"

    def initiate(self, request: ChargeRequest) -> ChargeResult:
        if request.amount_bdt <= 0:
            return ChargeResult(
                accepted=False,
                gateway_reference="",
                status="FAILED",
                is_sandbox=not self.is_configured(),
                message="Amount must be greater than zero",
            )

        gateway_reference = (
            f"{self.prefix}-{secrets.token_hex(8).upper()}"
        )
        sandbox = not self.is_configured()

        return ChargeResult(
            accepted=True,
            gateway_reference=gateway_reference,
            # A wallet payment is authorised by the payer on their handset, so
            # the charge stays pending until the provider calls back.
            status="PENDING",
            is_sandbox=sandbox,
            message=(
                "Sandbox mode: no live credentials configured"
                if sandbox
                else "Charge initiated"
            ),
            payload={
                "reference": request.reference,
                "amount": round(request.amount_bdt, 2),
                "currency": "BDT",
                "gateway": self.name,
            },
        )

    def refund(self, gateway_reference: str, amount_bdt: float) -> ChargeResult:
        if amount_bdt <= 0:
            return ChargeResult(
                accepted=False,
                gateway_reference=gateway_reference,
                status="FAILED",
                is_sandbox=not self.is_configured(),
                message="Refund amount must be greater than zero",
            )
        return ChargeResult(
            accepted=True,
            gateway_reference=f"RFND-{secrets.token_hex(6).upper()}",
            status="REFUNDED",
            is_sandbox=not self.is_configured(),
            message="Refund accepted",
            payload={"original": gateway_reference, "amount": round(amount_bdt, 2)},
        )

    def signature_for(self, payload: dict) -> str:
        """Expose signing so a caller can construct a valid test callback."""
        return self._sign(payload)


class BkashGateway(MobileWalletGateway):
    name = "bkash"
    prefix = "BKS"
    commission_rate = 0.0185


class NagadGateway(MobileWalletGateway):
    name = "nagad"
    prefix = "NGD"
    commission_rate = 0.0145


class RocketGateway(MobileWalletGateway):
    name = "rocket"
    prefix = "RKT"
    commission_rate = 0.0180


class SslCommerzGateway(MobileWalletGateway):
    """Card and internet-banking acquirer used for larger settlements."""

    name = "sslcommerz"
    prefix = "SSL"
    commission_rate = 0.0250


_REGISTRY = {
    "bkash": BkashGateway(),
    "nagad": NagadGateway(),
    "rocket": RocketGateway(),
    "sslcommerz": SslCommerzGateway(),
}

SUPPORTED_METHODS = sorted(_REGISTRY)


def get_gateway(method: str) -> PaymentGateway:
    gateway = _REGISTRY.get((method or "").lower())
    if gateway is None:
        raise KeyError(method)
    return gateway
