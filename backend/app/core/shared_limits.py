"""Atomic rate-limit counters shared by processes using one database."""
import hashlib
import hmac
import time

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.rate_limit import RateLimitWindow


def check_database_limit(client, limit, sessions=SessionLocal, timestamp=None):
    now = int(time.time() if timestamp is None else timestamp)
    window = now - now % 60
    hashed = hmac.new(settings.secret_key.encode(), client.encode(), hashlib.sha256).hexdigest()
    with sessions() as db:
        insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
        table = RateLimitWindow.__table__
        statement = insert(table).values(client_hash=hashed, window_start=window, requests=1)
        statement = statement.on_conflict_do_update(
            index_elements=[table.c.client_hash, table.c.window_start],
            set_={"requests": table.c.requests + 1},
        ).returning(table.c.requests)
        count = db.execute(statement).scalar_one()
        # Only the first request from a client in a window performs retention cleanup.
        if count == 1:
            db.execute(delete(RateLimitWindow).where(RateLimitWindow.window_start < window - 60))
        db.commit()
    return 0 if count <= limit else max(1, window + 60 - now)
