"""One-time account links and rotating refresh sessions."""
import hashlib
import os
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import quote, urlparse

from fastapi import HTTPException
from sqlalchemy import delete, update

from app.core.security import create_access_token, hash_password
from app.models.account_token import AccountToken
from app.models.user import User

_DEMO_OUTBOX = []


def email_mode():
    from app.core.config import settings
    return os.environ.get("ACCOUNT_EMAIL_MODE", "demo" if settings.app_env == "development" else "disabled")


def _now():
    return datetime.now(timezone.utc)


def issue(user, purpose, db):
    db.execute(delete(AccountToken).where(AccountToken.expires_at < _now()))
    raw = secrets.token_urlsafe(48)
    lifetime = timedelta(days=7) if purpose == "refresh" else timedelta(minutes=30)
    db.add(AccountToken(token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                        user_id=user.id, purpose=purpose, token_version=user.token_version,
                        expires_at=_now() + lifetime))
    return raw


def consume(raw, purpose, db):
    digest = hashlib.sha256(raw.encode()).hexdigest()
    now = _now()
    # An atomic update makes replay lose even when requests arrive together.
    result = db.execute(update(AccountToken).where(
        AccountToken.token_hash == digest, AccountToken.purpose == purpose,
        AccountToken.consumed_at.is_(None), AccountToken.expires_at > now,
    ).values(consumed_at=now))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid or expired link. Request a new one.")
    record = db.get(AccountToken, digest)
    user = db.query(User).filter(User.id == record.user_id).with_for_update().first()
    if not user or not user.is_active or user.token_version != record.token_version:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid or expired link. Request a new one.")
    return user


def session_tokens(user, db):
    access = create_access_token({"sub": user.id, "role": user.role, "ver": user.token_version})
    refresh = issue(user, "refresh", db)
    db.commit()
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


def deliver_link(email, purpose, raw):
    """SMTP is explicit: never return or log a password-reset credential."""
    host = os.environ.get("SMTP_HOST", "")
    sender = os.environ.get("SMTP_FROM", "")
    origin = os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
    parsed = urlparse(origin)
    if not host or not sender or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=503, detail="Account email delivery is not configured")
    link = f"{origin}/account-action.html#purpose={purpose}&token={quote(raw)}"
    message = EmailMessage()
    message["From"] = sender
    message["To"] = email
    message["Subject"] = "SasthoSetu: " + ("reset password" if purpose == "reset" else "verify email")
    message.set_content(f"Open this link within 30 minutes:\n{link}\n\n"
                        "If you did not request this, ignore this message.")
    try:
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            username = os.environ.get("SMTP_USERNAME", "")
            if username:
                smtp.login(username, os.environ.get("SMTP_PASSWORD", ""))
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise HTTPException(status_code=503, detail="Email delivery is unavailable. Try again later.") from error


def request_link(email, purpose, db):
    # Same configuration failure for known and unknown addresses.
    mode = email_mode()
    if mode not in {"demo", "smtp"} or (mode == "smtp" and not all(
            os.environ.get(k) for k in ("SMTP_HOST", "SMTP_FROM", "PUBLIC_APP_URL"))):
        raise HTTPException(status_code=503, detail="Account email delivery is not configured")
    generic = {"message": "If the account is eligible, an email will arrive shortly."}
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active or (purpose == "verify" and user.is_verified):
        return generic
    # Per-account cooldown applies even when public routes have many clients.
    recent = db.query(AccountToken.token_hash).filter(
        AccountToken.user_id == user.id, AccountToken.purpose == purpose,
        AccountToken.expires_at > _now() + timedelta(minutes=29),
    ).first()
    if recent:
        return generic
    raw = issue(user, purpose, db)
    try:
        if mode == "demo":
            _DEMO_OUTBOX[:] = [item for item in _DEMO_OUTBOX if item["expires_at"] > _now()]
            _DEMO_OUTBOX.append({"recipient": user.email, "purpose": purpose,
                                 "link": f"account-action.html#purpose={purpose}&token={quote(raw)}",
                                 "expires_at": _now() + timedelta(minutes=30)})
            del _DEMO_OUTBOX[:-100]
        else:
            deliver_link(user.email, purpose, raw)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return generic


def reset_password(raw, password, db):
    user = consume(raw, "reset", db)
    user.password_hash = hash_password(password)
    user.token_version += 1
    db.commit()
    return {"message": "Password reset. Sign in with your new password."}
