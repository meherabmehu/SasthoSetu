# -*- coding: utf-8 -*-
"""Application configuration (environment-driven)."""
from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    APP_NAME: str = "SasthoSetu"
    API_V1_PREFIX: str = "/v1"
    ENV: str = os.getenv("SASTHOSETU_ENV", "development")

    # SQLite fallback keeps local dev + CI zero-config; use PostgreSQL in prod
    # (see .env.example and docker-compose.yml).
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite:///./sasthosetu.db")

    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    # HMAC key for e-prescription QR signing (rotate in production)
    PRESCRIPTION_SIGNING_KEY: str = os.getenv(
        "PRESCRIPTION_SIGNING_KEY", "sasthosetu-rx-demo-key")

    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
