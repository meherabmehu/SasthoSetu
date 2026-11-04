"""Authenticated HTTP checks against a locally migrated/seeded demo server.

Keeps tokens in memory and checks anonymous rejection separately. Never runs
against a hosted application or changes a patient's medical record.
"""
import argparse
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse


def run(base):
    if urlparse(base).hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("Only run against a disposable local demo server")

    def request(path, payload=None, token=None, expected=200):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(base + path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                body, status = response.read(), response.status
        except urllib.error.HTTPError as error:
            body, status = error.read(), error.code
        if status != expected:
            raise AssertionError(f"{path}: expected {expected}, got {status}: {body[:300]!r}")
        return json.loads(body)

    assert request("/health")["status"] == "healthy"
    triage = {"symptoms": "বুকে ব্যথা, শ্বাস নিতে কষ্ট", "age_years": 50}
    request("/api/v1/triage", triage, expected=401)
    login = request("/api/v1/auth/login", {
        "email": os.environ.get("SMOKE_EMAIL", "patient@sasthosetu.gov.bd"),
        "password": os.environ.get("SMOKE_PASSWORD", "Patient@12345"),
    })
    token = login["access_token"]
    result = request("/api/v1/triage", triage, token)
    assert result["triage_level"] == "EMERGENCY", "Emergency rule did not escalate"
    result = request("/api/v1/ai/triage-ml", {
        "symptoms": "তিন দিন ধরে জ্বর ও কাশি", "age_years": 30}, token)
    assert "severity_level" in result
    result = request("/api/v1/hospitals/H001/surge-forecast", token=token)
    assert result["wards"], "No ward forecasts returned"
    assert all({point["hours_ahead"] for point in ward["forecast"]} == {24, 48, 72}
               for ward in result["wards"])
    assert result["is_live"] is False
    result = request("/api/v1/ai/drug-check", {"drugs": ["Warfin", "Ecosprin"]}, token)
    assert result["highest_severity"] == "major"
    assert request("/api/v1/fhir/metadata")["fhirVersion"] == "4.0.1"
    print("HTTP smoke passed: anonymous triage rejected; authenticated emergency, ML, surge, drug and public FHIR checks passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    run(args.base.rstrip("/"))
