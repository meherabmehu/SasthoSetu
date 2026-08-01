import unittest

from app.core.config import BACKEND_DIR, DEVELOPMENT_SECRET, Settings


BASE_ENV = {
    "DATABASE_URL": "sqlite:///./test.db",
}


class SettingsTests(unittest.TestCase):
    def test_development_defaults_are_runnable(self):
        settings = Settings.from_env(BASE_ENV)

        self.assertEqual(settings.app_env, "development")
        self.assertEqual(settings.secret_key, DEVELOPMENT_SECRET)
        self.assertEqual(settings.jwt_algorithm, "HS256")
        self.assertEqual(settings.access_token_expire_minutes, 60)

    def test_database_url_is_required(self):
        with self.assertRaisesRegex(ValueError, "DATABASE_URL is required"):
            Settings.from_env({})

    def test_production_rejects_development_secret(self):
        with self.assertRaisesRegex(ValueError, "SECRET_KEY"):
            Settings.from_env(
                {
                    **BASE_ENV,
                    "APP_ENV": "production",
                }
            )

    def test_production_accepts_strong_explicit_secret(self):
        settings = Settings.from_env(
            {
                **BASE_ENV,
                "APP_ENV": "production",
                "SECRET_KEY": "a-secure-production-secret-with-32-characters",
            }
        )

        self.assertEqual(settings.app_env, "production")

    def test_invalid_boolean_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "APP_DEBUG"):
            Settings.from_env(
                {
                    **BASE_ENV,
                    "APP_DEBUG": "sometimes",
                }
            )

    def test_invalid_token_lifetime_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "ACCESS_TOKEN_EXPIRE_MINUTES",
        ):
            Settings.from_env(
                {
                    **BASE_ENV,
                    "ACCESS_TOKEN_EXPIRE_MINUTES": "0",
                }
            )


class SqlitePathTests(unittest.TestCase):
    """A relative SQLite path must mean the same file from any directory.

    Migrations run from ``backend/`` while the seed script runs from the
    repository root; without anchoring, those two commands would populate
    different database files and the seed would appear to silently fail.
    """

    def test_relative_sqlite_path_is_anchored_to_the_backend_directory(self):
        settings = Settings.from_env({"DATABASE_URL": "sqlite:///./dev.db"})
        expected = (BACKEND_DIR / "dev.db").resolve()
        self.assertEqual(f"sqlite:///{expected}", settings.database_url)

    def test_absolute_sqlite_path_is_left_alone(self):
        url = "sqlite:////var/lib/sasthosetu/app.db"
        self.assertEqual(url, Settings.from_env({"DATABASE_URL": url}).database_url)

    def test_in_memory_database_is_left_alone(self):
        url = "sqlite:///:memory:"
        self.assertEqual(url, Settings.from_env({"DATABASE_URL": url}).database_url)

    def test_postgres_url_is_left_alone(self):
        url = "postgresql+psycopg2://user:pass@localhost:5432/sasthosetu"
        self.assertEqual(url, Settings.from_env({"DATABASE_URL": url}).database_url)


if __name__ == "__main__":
    unittest.main()
