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


class CorsOriginTests(unittest.TestCase):
    """Local development must not depend on one hard-coded port.

    Serving the frontend from a port that was not in the allowlist produced a
    CORS preflight rejection, which the page reported as "no internet
    connection" — a misleading message for a configuration mismatch.
    """

    def _matches(self, settings, origin):
        import re

        return bool(
            settings.cors_origin_regex
            and re.match(settings.cors_origin_regex, origin)
        )

    def test_any_loopback_port_is_allowed_in_development(self):
        settings = Settings.from_env(BASE_ENV)

        for origin in (
            "http://localhost:5500",
            "http://localhost:5501",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
            "http://[::1]:5501",
            "http://localhost",
        ):
            with self.subTest(origin=origin):
                self.assertTrue(self._matches(settings, origin))

    def test_lookalike_hosts_are_rejected(self):
        settings = Settings.from_env(BASE_ENV)

        for origin in (
            "http://evil.com",
            "http://localhost.attacker.net",
            "https://localhost.evil.com",
            "http://notlocalhost:5501",
            "http://127.0.0.1.evil.com",
        ):
            with self.subTest(origin=origin):
                self.assertFalse(self._matches(settings, origin))

    def test_production_has_no_implicit_localhost_allowance(self):
        settings = Settings.from_env({
            **BASE_ENV,
            "APP_ENV": "production",
            "SECRET_KEY": "x" * 40,
        })
        self.assertIsNone(settings.cors_origin_regex)

    def test_an_explicit_regex_always_wins(self):
        pattern = r"^https://app\.sasthosetu\.gov\.bd$"
        settings = Settings.from_env({
            **BASE_ENV,
            "APP_ENV": "production",
            "SECRET_KEY": "x" * 40,
            "CORS_ORIGIN_REGEX": pattern,
        })
        self.assertEqual(pattern, settings.cors_origin_regex)


if __name__ == "__main__":
    unittest.main()
