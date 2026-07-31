import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"
DEVELOPMENT_SECRET = "development-only-secret-change-before-production"

load_dotenv(ENV_FILE)


def _positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return parsed


def _boolean(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _rate(value: str, name: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a number") from error
    if not 0 <= parsed < 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return parsed


def _csv(value: str) -> tuple[str, ...]:
    items = [item.strip() for item in (value or "").split(",") if item.strip()]
    return tuple(items) or ("*",)


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    app_env: str
    debug: bool
    database_url: str
    secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    platform_commission_rate: float
    cors_origins: tuple[str, ...]
    rate_limit_per_minute: int
    bkash_api_key: str
    bkash_api_secret: str
    nagad_api_key: str
    nagad_api_secret: str
    rocket_api_key: str
    rocket_api_secret: str
    sslcommerz_api_key: str
    sslcommerz_api_secret: str

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "Settings":
        values = os.environ if environ is None else environ
        app_env = values.get("APP_ENV", "development").strip().lower()
        if app_env not in {"development", "test", "staging", "production"}:
            raise ValueError(
                "APP_ENV must be development, test, staging, or production"
            )

        database_url = values.get("DATABASE_URL", "").strip()
        if not database_url:
            raise ValueError("DATABASE_URL is required")

        secret_key = values.get("SECRET_KEY", DEVELOPMENT_SECRET).strip()
        if app_env in {"staging", "production"}:
            if secret_key == DEVELOPMENT_SECRET or len(secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be explicitly set to at least 32 "
                    "characters in staging and production"
                )

        jwt_algorithm = values.get("JWT_ALGORITHM", "HS256").strip()
        if jwt_algorithm not in {"HS256", "HS384", "HS512"}:
            raise ValueError("JWT_ALGORITHM must be HS256, HS384, or HS512")

        return cls(
            app_name=values.get("APP_NAME", "SasthoSetu API").strip(),
            app_version=values.get("APP_VERSION", "1.0.0").strip(),
            app_env=app_env,
            debug=_boolean(values.get("APP_DEBUG", "false"), "APP_DEBUG"),
            database_url=database_url,
            secret_key=secret_key,
            jwt_algorithm=jwt_algorithm,
            access_token_expire_minutes=_positive_int(
                values.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"),
                "ACCESS_TOKEN_EXPIRE_MINUTES",
            ),
            platform_commission_rate=_rate(
                values.get("PLATFORM_COMMISSION_RATE", "0.02"),
                "PLATFORM_COMMISSION_RATE",
            ),
            cors_origins=_csv(values.get("CORS_ORIGINS", "*")),
            rate_limit_per_minute=_positive_int(
                values.get("RATE_LIMIT_PER_MINUTE", "120"),
                "RATE_LIMIT_PER_MINUTE",
            ),
            bkash_api_key=values.get("BKASH_API_KEY", "").strip(),
            bkash_api_secret=values.get("BKASH_API_SECRET", "").strip(),
            nagad_api_key=values.get("NAGAD_API_KEY", "").strip(),
            nagad_api_secret=values.get("NAGAD_API_SECRET", "").strip(),
            rocket_api_key=values.get("ROCKET_API_KEY", "").strip(),
            rocket_api_secret=values.get("ROCKET_API_SECRET", "").strip(),
            sslcommerz_api_key=values.get("SSLCOMMERZ_API_KEY", "").strip(),
            sslcommerz_api_secret=values.get("SSLCOMMERZ_API_SECRET", "").strip(),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()


settings = get_settings()