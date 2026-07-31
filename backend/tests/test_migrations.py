import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import BACKEND_DIR


EXPECTED_TABLES = {
    "ai_feedback",
    "alembic_version",
    "appointments",
    "bed_status_history",
    "doctor_availability",
    "doctors",
    "file_records",
    "medical_records",
    "notifications",
    "patients",
    "hospital_staff",
    "hospitals",
    "prescriptions",
    "users",
    "wards",
}


class MigrationTests(unittest.TestCase):
    def test_initial_migration_upgrades_and_downgrades_clean_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "migration_test.db"
            database_url = f"sqlite:///{database_path.as_posix()}"
            config = Config(str(BACKEND_DIR / "alembic.ini"))
            config.attributes["database_url"] = database_url

            command.upgrade(config, "head")

            engine = create_engine(database_url)
            self.assertEqual(
                set(inspect(engine).get_table_names()),
                EXPECTED_TABLES,
            )
            engine.dispose()

            command.check(config)
            command.downgrade(config, "base")

            engine = create_engine(database_url)
            self.assertEqual(
                set(inspect(engine).get_table_names()),
                {"alembic_version"},
            )
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
