"""Operational alerts must be aggregate-only and disabled by default."""
import os
import tempfile
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/operations.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from app.operations.alerts import dispatch_alerts, evaluate_alerts, webhook_status  # noqa: E402


class OperationsAlertTests(unittest.TestCase):
    def test_thresholds_create_aggregate_alerts(self):
        alerts = evaluate_alerts({"total": 10, "errors": 1, "average_latency_ms": 3000})
        self.assertEqual({"error_rate", "latency"}, {alert["kind"] for alert in alerts})
        self.assertNotIn("symptoms", str(alerts).lower())

    def test_delivery_stays_disabled_without_a_valid_enabled_https_webhook(self):
        status = webhook_status()
        self.assertFalse(status["enabled"])
        result = dispatch_alerts([{"kind": "latency"}], release={"git_commit": "test"})
        self.assertEqual(0, result["sent"])
