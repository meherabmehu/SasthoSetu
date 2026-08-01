# -*- coding: utf-8 -*-
"""Schema drift must announce itself, not surface as an opaque 500.

Pulling new code without running the migration is the most common way to break
a working checkout. Before this, it produced a 500 and a long SQLAlchemy
traceback pointing at the query rather than the cause.
"""
import os
import unittest

os.environ["APP_ENV"] = "test"
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_schema.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from app.core.schema_check import MIGRATION_COMMAND, missing_tables  # noqa: E402


class SchemaCheckTests(unittest.TestCase):
    def test_a_fully_migrated_database_reports_nothing_missing(self):
        from app.core.database import engine
        from app.models.base import Base

        Base.metadata.create_all(bind=engine)
        self.assertEqual([], missing_tables())

    def test_the_reviews_tables_are_part_of_the_expected_schema(self):
        """These are the tables a stale checkout is missing."""
        from app.models.base import Base

        expected = set(Base.metadata.tables)
        self.assertIn("doctor_reviews", expected)
        self.assertIn("doctor_rating_summaries", expected)

    def test_the_advice_names_the_command_to_run(self):
        self.assertIn("alembic upgrade head", MIGRATION_COMMAND)


if __name__ == "__main__":
    unittest.main()
