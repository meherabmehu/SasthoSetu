# -*- coding: utf-8 -*-
"""Bring the database schema up to date.

A long-running deployment does this from the container entrypoint before the
server starts. A serverless deployment has no such moment: every instance
begins with one request and ends with it, so the schema has to be settled
from the build step instead.

    DATABASE_URL=postgresql+psycopg2://... python scripts/migrate.py

Safe to run repeatedly. Alembic applies only what is missing, so a build that
changes nothing about the schema is a no-op.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def main() -> int:
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        print(
            "DATABASE_URL is not set, so there is no schema to migrate.\n"
            "Set it to the database the deployment will use.",
            file=sys.stderr,
        )
        return 1

    if url.startswith("sqlite"):
        print(
            "DATABASE_URL points at SQLite. A serverless deployment cannot "
            "keep a SQLite file: it is discarded when the instance ends, so "
            "every write would be lost. Use Postgres.",
            file=sys.stderr,
        )
        return 1

    sys.path.insert(0, str(BACKEND))

    from alembic import command
    from alembic.config import Config

    # Through the same normalisation the application uses, so a URL supplied
    # by a hosting integration migrates and serves identically.
    from app.core.config import _normalise_postgres_driver

    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    config.set_main_option(
        "sqlalchemy.url", _normalise_postgres_driver(url))

    command.upgrade(config, "head")
    print("Schema is up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
