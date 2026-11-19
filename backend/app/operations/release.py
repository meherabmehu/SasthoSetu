"""Safe release metadata for an operator dashboard."""
from __future__ import annotations

import os

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings


def release_status(db: Session) -> dict:
    """Expose no secret; absent CI metadata is labelled rather than invented."""
    revision = None
    try:
        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:
        revision = "unavailable"
    return {
        "app_version": settings.app_version,
        "environment": settings.app_env,
        "git_commit": os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("GIT_SHA") or "not_supplied",
        "build_time": os.environ.get("BUILD_TIME") or "not_supplied",
        "migration_revision": revision or "not_applied",
        "sentry_configured": bool(settings.sentry_dsn),
    }
