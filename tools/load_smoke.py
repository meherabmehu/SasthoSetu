"""Small local concurrency smoke check; not a production capacity benchmark."""
import json
import os
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse


def run():
    base = os.environ.get("QA_BASE_URL", "http://127.0.0.1:8765")
    if urlparse(base).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("This smoke test targets a local fixture server only")

    def request(_):
        started = time.perf_counter()
        with urllib.request.urlopen(base + "/fhir/metadata", timeout=10) as response:
            response.read()
            if response.status != 200:
                raise RuntimeError("Non-200 response")
        return time.perf_counter() - started

    # The actual public API path is /api/v1/fhir/metadata.
    base = base.rstrip("/") + "/api/v1"
    with ThreadPoolExecutor(max_workers=8) as pool:
        durations = list(pool.map(request, range(40)))
    print(json.dumps({"requests": len(durations), "concurrency": 8, "errors": 0,
        "median_ms": round(statistics.median(durations) * 1000, 1),
        "max_ms": round(max(durations) * 1000, 1), "scope": "local_fixture_only"}))


if __name__ == "__main__":
    run()
