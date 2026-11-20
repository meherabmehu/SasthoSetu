"""Live documentation API with server-enforced publication controls."""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import require_admin
from app.models.ai_inference_event import AIInferenceEvent
from app.models.doctor import Doctor
from app.models.docs_publication import DocsPublication, DocsPublicationVersion
from app.models.hospital import Hospital
from app.models.user import User

router = APIRouter()

DEFAULT_CONTENT = {
    "team_name": "SasthoSetu",
    "team": [],
    "sections": {
        "problem": "Finding the right care can be difficult when symptoms are unclear, information is fragmented, and language creates an additional barrier.",
        "solution": "SasthoSetu helps people move from a health concern to a safer next action through Bangla first triage, trusted information, and local care navigation.",
        "vision": "Make reliable care navigation easier to understand and reach for every person in Bangladesh.",
    },
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _publication(db: Session) -> DocsPublication:
    row = db.get(DocsPublication, 1)
    if row is None:
        row = DocsPublication(id=1, content_json=json.dumps(DEFAULT_CONTENT), public_enabled=True)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _is_public(row: DocsPublication) -> bool:
    now = _now()
    start = row.starts_at
    end = row.ends_at
    if start is not None and start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end is not None and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return bool(row.public_enabled and (start is None or now >= start) and (end is None or now <= end))


def _content(row: DocsPublication) -> dict:
    try:
        value = json.loads(row.content_json)
        return value if isinstance(value, dict) else DEFAULT_CONTENT
    except (TypeError, ValueError):
        return DEFAULT_CONTENT


def _live_state(db: Session) -> dict:
    """Only aggregate public metrics are exposed: no patient data ever leaves here."""
    return {
        "users": db.query(User).filter(User.is_active.is_(True)).count(),
        "hospitals": db.query(Hospital).count(),
        "doctors": db.query(Doctor).filter(Doctor.verification_status.is_(True)).count(),
        "ai_events": db.query(AIInferenceEvent).count(),
        "updated_at": _now().isoformat(),
        "data_notice": "Live figures are aggregate counts only. No personal health information is included.",
    }


def _payload(row: DocsPublication, db: Session, *, include_live: bool = True) -> dict:
    return {
        "public_enabled": row.public_enabled,
        "starts_at": row.starts_at.isoformat() if row.starts_at else None,
        "ends_at": row.ends_at.isoformat() if row.ends_at else None,
        "is_available": _is_public(row),
        "version": row.version,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "content": _content(row),
        "live": _live_state(db) if include_live else None,
    }


@router.get("/docs/public")
def public_docs(db: Session = Depends(get_db)):
    row = _publication(db)
    if not _is_public(row):
        raise HTTPException(status_code=404, detail="Documentation is not available at this time.")
    return _payload(row, db)


@router.get("/docs/export")
def export_docs(
    format: str = Query("markdown", pattern="^(markdown|json)$"),
    db: Session = Depends(get_db),
):
    row = _publication(db)
    if not _is_public(row):
        raise HTTPException(status_code=404, detail="Documentation is not available at this time.")
    payload = _payload(row, db)
    if format == "json":
        return payload
    content = payload["content"]
    sections = content.get("sections", {})
    lines = ["# SasthoSetu", "", "## Live documentation", ""]
    for name, text in sections.items():
        lines.extend([f"## {str(name).replace('_', ' ').title()}", str(text), ""])
    lines.extend(["## Live system summary", json.dumps(payload["live"], indent=2)])
    return {"format": "markdown", "content": "\n".join(lines)}


@router.get("/admin/docs/config", dependencies=[Depends(require_admin)])
def admin_docs_config(db: Session = Depends(get_db)):
    return _payload(_publication(db), db)


@router.put("/admin/docs/config", dependencies=[Depends(require_admin)])
def update_docs_config(payload: dict, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    row = _publication(db)
    allowed = {"public_enabled", "starts_at", "ends_at", "content"}
    unknown = set(payload) - allowed
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unsupported fields: {', '.join(sorted(unknown))}")

    def parse_time(value):
        if value in (None, ""):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as error:
            raise HTTPException(status_code=422, detail="Dates must be ISO 8601 timestamps") from error
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    starts_at = parse_time(payload.get("starts_at", row.starts_at.isoformat() if row.starts_at else None))
    ends_at = parse_time(payload.get("ends_at", row.ends_at.isoformat() if row.ends_at else None))
    if starts_at and ends_at and starts_at >= ends_at:
        raise HTTPException(status_code=422, detail="The publishing end time must be after the start time")

    old_content = row.content_json
    if "content" in payload:
        if not isinstance(payload["content"], dict):
            raise HTTPException(status_code=422, detail="Content must be an object")
        row.content_json = json.dumps(payload["content"])
    row.public_enabled = bool(payload.get("public_enabled", row.public_enabled))
    row.starts_at, row.ends_at = starts_at, ends_at
    row.version += 1
    row.updated_at = _now()
    db.add(DocsPublicationVersion(
        publication_id=row.id, version=row.version, content_json=old_content,
        created_by=current_user.get("user_id"),
    ))
    db.commit()
    db.refresh(row)
    return _payload(row, db)


@router.get("/admin/docs/versions", dependencies=[Depends(require_admin)])
def docs_versions(db: Session = Depends(get_db)):
    _publication(db)
    rows = db.query(DocsPublicationVersion).order_by(DocsPublicationVersion.created_at.desc()).limit(20).all()
    return [{"version": row.version, "created_at": row.created_at.isoformat(), "created_by": row.created_by} for row in rows]
