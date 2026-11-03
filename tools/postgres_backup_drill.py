"""Rehearse pg_dump/pg_restore in a disposable schema of TEST_POSTGRES_URL.

Creates its own sentinel table, dumps it, drops only that generated schema,
restores it and compares the sentinel. Never targets application tables.
PG_BIN may specify a directory containing pg_dump/pg_restore on Windows.
"""
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def run():
    raw = os.environ.get("TEST_POSTGRES_URL")
    if not raw:
        raise SystemExit("Set TEST_POSTGRES_URL to a disposable test database")
    url = make_url(raw)
    schema = "drill_" + uuid.uuid4().hex
    sentinel = uuid.uuid4().hex
    env = dict(os.environ, PGHOST=url.host or "localhost", PGPORT=str(url.port or 5432),
               PGDATABASE=url.database or "postgres", PGUSER=url.username or "postgres",
               PGPASSWORD=url.password or "")
    binary_dir = Path(os.environ.get("PG_BIN", ""))
    dump_bin = str(binary_dir / "pg_dump") if str(binary_dir) != "." else "pg_dump"
    restore_bin = str(binary_dir / "pg_restore") if str(binary_dir) != "." else "pg_restore"
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            conn.execute(text(f'CREATE TABLE "{schema}".sentinel (value TEXT NOT NULL)'))
            conn.execute(text(f'INSERT INTO "{schema}".sentinel VALUES (:value)'), {"value": sentinel})
        with tempfile.TemporaryDirectory() as folder:
            archive = str(Path(folder) / "drill.dump")
            subprocess.run([dump_bin, "--no-password", "--format=custom", "--schema=" + schema,
                            "--file=" + archive], env=env, check=True, capture_output=True)
            with engine.begin() as conn:
                conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            subprocess.run([restore_bin, "--no-password", "--exit-on-error", "--no-owner",
                            "--dbname=" + env["PGDATABASE"], archive], env=env,
                           check=True, capture_output=True)
            with engine.connect() as conn:
                actual = conn.execute(text(f'SELECT value FROM "{schema}".sentinel')).scalar_one()
            if actual != sentinel:
                raise RuntimeError("Restored sentinel differs from original")
        print("PostgreSQL backup/restore drill passed in a disposable schema.")
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()


if __name__ == "__main__":
    run()
