# -*- coding: utf-8 -*-
"""Assemble the static frontend for a hosted deployment.

The frontend is plain HTML and runs unbuilt during development, where it
finds the API on the conventional port of the same host. A hosted deployment
breaks that assumption: the pages are served from a CDN and the API lives on
another domain entirely, so the address has to be written into the pages.

This copies frontend/ to frontend/dist/ and stamps every page with

    <meta name="api-base" content="...">

which assets/js/api.js already looks for ahead of its own guesswork.

    API_BASE_URL=https://api.example.com python scripts/build_frontend.py

The trailing /api/v1 is added if it is missing, so either form works.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend"
OUT = SRC / "dist"

API_SUFFIX = "/api/v1"

# Written just after the viewport tag, which every page in this project has.
ANCHOR = re.compile(
    r'(<meta\s+name="viewport"[^>]*>)', re.I)

EXISTING = re.compile(
    r'\s*<meta\s+name="api-base"[^>]*>', re.I)


def api_base() -> str:
    raw = (os.environ.get("API_BASE_URL") or "").strip().rstrip("/")
    if not raw:
        raise SystemExit(
            "API_BASE_URL is not set. The deployed pages would fall back to\n"
            "the local development address and every request would fail.\n"
            "Set it to the public address of the backend, for example:\n"
            "  API_BASE_URL=https://sasthosetu-api.up.railway.app"
        )
    if not raw.startswith(("http://", "https://")):
        raise SystemExit(
            f"API_BASE_URL must include the scheme, got: {raw}")
    if raw.endswith(API_SUFFIX):
        return raw
    return raw + API_SUFFIX


def stamp(html: str, base: str) -> str:
    """Put the API address into a page, replacing any address already there."""
    html = EXISTING.sub("", html)
    tag = f'\n<meta name="api-base" content="{base}">'
    if not ANCHOR.search(html):
        raise RuntimeError("no viewport meta tag to anchor against")
    return ANCHOR.sub(lambda m: m.group(1) + tag, html, count=1)


def main() -> None:
    base = api_base()

    if OUT.exists():
        shutil.rmtree(OUT)
    # dist lives inside frontend/, so it must be excluded from its own copy.
    shutil.copytree(SRC, OUT, ignore=shutil.ignore_patterns("dist"))

    pages = sorted(OUT.glob("*.html"))
    if not pages:
        raise SystemExit("no pages were copied - is frontend/ populated?")

    for page in pages:
        html = page.read_text(encoding="utf-8")
        page.write_text(stamp(html, base), encoding="utf-8")

    print(f"api base   {base}")
    print(f"stamped    {len(pages)} pages -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
