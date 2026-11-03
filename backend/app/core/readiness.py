"""Readiness is separate from the process liveness endpoint."""
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text

from app.ai.artifact_loading import load_artifact
from app.core.database import engine
from app.models.base import Base

router = APIRouter()
ART = Path(__file__).resolve().parents[1] / "ai" / "artifacts"


@router.get("/ready")
def readiness():
    checks = {}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            inspector = inspect(connection)
            checks["database"] = all(
                inspector.has_table(table.name) and
                set(table.columns.keys()) <= {col["name"] for col in inspector.get_columns(table.name)}
                for table in Base.metadata.sorted_tables
            )
    except Exception:
        checks["database"] = False
    for name in ("triage", "surge"):
        try:
            load_artifact(ART / f"{name}_model.joblib")
            checks[name] = True
        except Exception:
            checks[name] = False
    ready = all(checks.values())
    return JSONResponse({"status": "ready" if ready else "not_ready", "checks": checks},
                        status_code=200 if ready else 503)
