# -*- coding: utf-8 -*-
"""Serverless entrypoint.

Vercel imports ``app`` from this module and serves it for every path routed
here by vercel.json. The application itself is unchanged; this only puts the
backend package on the import path and states where the models live.

Startup work that a long-running server can do once - applying migrations,
training models - has no place here, because a serverless instance starts
for a single request and is discarded. Migrations run from the build step
instead (scripts/migrate.py), and the models are committed to the
repository so the function only has to load them.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import app  # noqa: E402,F401
