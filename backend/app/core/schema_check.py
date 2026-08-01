# -*- coding: utf-8 -*-
"""Startup check that the database schema matches the code.

Pulling new code without running the migration is the single most common way
to break a working checkout. Left unchecked it surfaces as an opaque 500 and a
long SQLAlchemy traceback at the moment a user clicks something, which points
at the query rather than at the actual cause.

This compares the tables the models expect against the tables that exist, and
says plainly what to run. It warns rather than refuses to start: an operator
debugging a half-migrated database should still be able to reach the health
endpoint and the API docs.
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect

from app.core.database import engine
from app.models.base import Base

logger = logging.getLogger("sasthosetu.schema")

MIGRATION_COMMAND = "cd backend && alembic upgrade head"


def missing_tables() -> list[str]:
    """Tables the models declare that the database does not have."""
    try:
        existing = set(inspect(engine).get_table_names())
    except Exception as error:  # noqa: BLE001 - a check must never break boot
        logger.warning("Could not inspect the database schema: %s", error)
        return []

    expected = set(Base.metadata.tables)
    return sorted(expected - existing)


def verify_schema() -> list[str]:
    """Log a clear, actionable message when the schema is behind the code."""
    missing = missing_tables()
    if not missing:
        return []

    listed = ", ".join(missing)
    logger.error(
        "DATABASE SCHEMA IS OUT OF DATE. Missing %d table(s): %s. "
        "Requests touching these will fail. Fix it by running:  %s",
        len(missing),
        listed,
        MIGRATION_COMMAND,
    )
    return missing
