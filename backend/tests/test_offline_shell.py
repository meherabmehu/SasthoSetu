# -*- coding: utf-8 -*-
"""The service worker must keep pace with the pages it is caching for.

Two failures hide here, and neither shows up in development, where the
network is fast and the cache is usually empty:

  - A page added to the app but not to the shell list is unreachable
    offline. The reader gets the offline fallback for a page that was
    downloaded and works.

  - A change to the caching rules that does not raise VERSION leaves every
    returning visitor on the previous service worker, serving the previous
    app from their own disk, indefinitely.

The third test covers a confidentiality rule rather than a caching one: the
data cache holds prescriptions and appointments, so signing out has to
discard it.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
WORKER = FRONTEND / "service-worker.js"
API_CLIENT = FRONTEND / "assets" / "js" / "api.js"

# Served only by the worker itself when a navigation fails, so it is never
# requested by name and does not belong in the navigable page list.
NOT_NAVIGABLE = {"offline.html"}


def shell_assets() -> set[str]:
    source = WORKER.read_text(encoding="utf-8")
    block = re.search(
        r"const SHELL_ASSETS\s*=\s*\[(.*?)\];", source, re.S)
    if not block:
        raise AssertionError("SHELL_ASSETS is missing from the service worker")
    return set(re.findall(r"'([^']+)'", block.group(1)))


class ServiceWorkerTests(unittest.TestCase):
    def test_every_page_is_available_offline(self):
        cached = shell_assets()
        pages = {
            path.name for path in FRONTEND.glob("*.html")
        } - NOT_NAVIGABLE

        missing = sorted(pages - cached)
        self.assertEqual(
            [], missing,
            "these pages are not in the service worker's shell list, so they "
            f"will not open without a connection: {missing}. Add them to "
            "SHELL_ASSETS in frontend/service-worker.js and raise VERSION.",
        )

    def test_the_shell_list_has_no_pages_that_no_longer_exist(self):
        cached = shell_assets()
        stale = sorted(
            name for name in cached
            if name.endswith(".html") and not (FRONTEND / name).exists()
        )
        self.assertEqual(
            [], stale,
            f"the service worker caches pages that are gone: {stale}",
        )

    def test_signing_out_discards_the_cached_api_responses(self):
        """Otherwise the next user of a shared phone can read them."""
        source = API_CLIENT.read_text(encoding="utf-8")

        clear = re.search(r"clear\(\)\s*\{(.*?)\n  \},", source, re.S)
        self.assertIsNotNone(clear, "session.clear() is missing")

        self.assertIn(
            "clearCachedResponses", clear.group(1),
            "session.clear() removes the token but leaves the service "
            "worker's cached API responses, which include prescriptions and "
            "appointments, readable by whoever uses the device next.",
        )
        self.assertIn(
            "caches.delete", source,
            "nothing in the API client deletes a cache, so the cached "
            "responses survive signing out",
        )


if __name__ == "__main__":
    unittest.main()
