# -*- coding: utf-8 -*-
"""Build step for a single-domain Vercel deployment.

Vercel runs this once per deployment, before the function is packaged. Two
things have to happen here because a serverless function cannot do them
itself - it starts for one request and is discarded, so there is no start-up
in which to apply a migration or train a model:

1. Bring the database schema up to date.
2. Assemble the static pages, pointing them at the API on the same domain.

The trained models are not built here. They are committed to the repository
precisely so that this step stays short; rebuilding them would add minutes
to every deployment and exceed the build time limit.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Same-origin: vercel.json rewrites /api/* to the function, so the pages
# address the API by path and every preview deployment works on its own
# hostname without further configuration.
DEFAULT_API_BASE = "/api/v1"


def run(label: str, args: list[str], env: dict[str, str]) -> None:
    print(f"\n=== {label}")
    result = subprocess.run(args, env=env, cwd=str(ROOT))
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    env = dict(os.environ)
    env.setdefault("API_BASE_URL", DEFAULT_API_BASE)

    if env.get("DATABASE_URL", "").strip():
        run("Database schema",
            [sys.executable, "scripts/migrate.py"], env)
    else:
        # Better to say so during the build than to let every request fail
        # later with a schema error that looks like a code bug.
        print(
            "\n=== Database schema\n"
            "DATABASE_URL is not set, so the schema was left alone. The "
            "deployment will build, but every request that touches the "
            "database will fail until it is configured."
        )

    run("Static pages",
        [sys.executable, "scripts/build_frontend.py"], env)


if __name__ == "__main__":
    main()
