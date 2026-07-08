import unittest

from app.core.config import DEVELOPMENT_SECRET, Settings


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


if __name__ == "__main__":
    unittest.main()
