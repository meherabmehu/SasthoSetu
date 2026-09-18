# -*- coding: utf-8 -*-
"""The migrations must run on Postgres, not only on SQLite.

Development uses SQLite and every deployment uses Postgres, so a migration
can pass the whole suite and still fail the moment it reaches a real
deployment. That is exactly what happened with

    was_overridden BOOLEAN DEFAULT 0

SQLite has no boolean type and accepts the integer. Postgres refuses it:

    column "was_overridden" is of type boolean but default expression is of
    type integer

The deploy failed on the first migration that created a triage_sessions
table, which meant no schema, no seed data and no working application.

These tests compile the migrations and the models against the Postgres
dialect. No server is needed - SQLAlchemy renders the same DDL that Postgres
would have received.
"""
import io
import re
import unittest
from contextlib import redirect_stdout
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

# Postgres rejects a bare 0 or 1 as the default for a boolean column.
NUMERIC_BOOL_DEFAULT = re.compile(r"DEFAULT\s+[01]\b", re.I)


POSTGRES_URL = "postgresql+psycopg2://user:pw@localhost/db"


def postgres_ddl_for_migrations() -> str:
    """The SQL the migrations would send to a Postgres server.

    The URL goes through config.attributes, which env.py prefers over the
    configured settings. Setting DATABASE_URL instead would not work here:
    settings are read once at import, and by the time this runs another test
    module has already loaded them pointing at SQLite.
    """
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    config.attributes["database_url"] = POSTGRES_URL

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        # Offline mode: render the SQL instead of connecting.
        command.upgrade(config, "head", sql=True)
    return buffer.getvalue()


def offending_lines(ddl: str) -> list[str]:
    return [
        line.strip()
        for line in ddl.splitlines()
        if "BOOLEAN" in line.upper() and NUMERIC_BOOL_DEFAULT.search(line)
    ]


class MigrationPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ddl = postgres_ddl_for_migrations()

    def test_the_whole_chain_renders_for_postgres(self):
        """A migration that only works under SQLite stops the chain here."""
        self.assertIn(
            "20260803_0007", self.ddl,
            "the migrations did not reach the latest revision under the "
            "Postgres dialect",
        )

    def test_no_boolean_column_defaults_to_an_integer(self):
        bad = offending_lines(self.ddl)
        self.assertEqual(
            [], bad,
            "Postgres rejects an integer default on a boolean column. Use "
            "sa.text('true') or sa.text('false'):\n  " + "\n  ".join(bad),
        )

    def test_every_boolean_default_is_a_keyword(self):
        """Confirms the check above is actually looking at something."""
        keyword_defaults = [
            line for line in self.ddl.splitlines()
            if "BOOLEAN" in line.upper()
            and re.search(r"DEFAULT\s+(true|false)\b", line, re.I)
        ]
        self.assertGreater(
            len(keyword_defaults), 10,
            "expected the schema to contain boolean columns with true/false "
            "defaults; if this fails the compatibility check may be "
            "inspecting the wrong output",
        )


class ModelPostgresTests(unittest.TestCase):
    def test_no_model_declares_an_integer_default_on_a_boolean(self):
        """create_all is used by the test suite and by a fresh install."""
        from sqlalchemy.dialects import postgresql
        from sqlalchemy.schema import CreateTable

        import app.models  # noqa: F401  - registers every table
        from app.models.base import Base

        dialect = postgresql.dialect()
        bad = []
        for name, table in Base.metadata.tables.items():
            ddl = str(CreateTable(table).compile(dialect=dialect))
            bad.extend(f"{name}: {line}" for line in offending_lines(ddl))

        self.assertEqual(
            [], bad,
            "these model columns would fail on Postgres:\n  "
            + "\n  ".join(bad),
        )


if __name__ == "__main__":
    unittest.main()
