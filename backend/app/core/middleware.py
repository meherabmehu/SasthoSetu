# -*- coding: utf-8 -*-
"""Cross-cutting HTTP middleware.

Three concerns handled here rather than in each route: request correlation and
timing, security response headers, and abuse control.
"""
from __future__ import annotations

import logging
import time
import uuid
from collections import deque

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = logging.getLogger("sasthosetu.request")

# Paths that must stay reachable even when a client is being rate limited,
# because they are how operators find out the service is unhealthy.
RATE_LIMIT_EXEMPT = {"/health", "/", "/openapi.json", "/docs", "/redoc"}

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(self), microphone=(), camera=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request id, log the outcome and report server timing."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except OperationalError as error:
            # Almost always a schema that is behind the code. Say so, rather
            # than returning a generic 500 that sends the reader into a
            # SQLAlchemy traceback looking for a bug that is not there.
            duration_ms = (time.perf_counter() - started) * 1000
            detail = str(error.orig) if error.orig else str(error)
            is_missing_table = "no such table" in detail.lower()

            logger.error(
                "database error on %s %s after %.1fms: %s",
                request.method,
                request.url.path,
                duration_ms,
                detail,
                extra={"request_id": request_id},
            )

            message = (
                "The database schema is out of date. Run: "
                "cd backend && alembic upgrade head"
                if is_missing_table
                else "A database error occurred."
            )
            return JSONResponse(
                status_code=503 if is_missing_table else 500,
                content={"detail": message, "request_id": request_id},
                headers={"X-Request-ID": request_id},
            )
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                "request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            # Never leak a stack trace to the caller.
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )

        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-ms"] = f"{duration_ms:.1f}"

        logger.info(
            "%s %s -> %s in %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={"request_id": request_id},
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)

        if settings.app_env in ("staging", "production"):
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window per-client request cap.

    Held in process memory, which is correct for a single instance and a
    conservative floor behind several. A shared store is the right answer once
    the API runs multi-node; the limit is enforced here so an unprotected
    deployment is never the default.
    """

    def __init__(self, app, limit_per_minute: int | None = None):
        super().__init__(app)
        self.limit = limit_per_minute or settings.rate_limit_per_minute
        self._hits: dict[str, deque] = {}

    def _client_key(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        if request.url.path in RATE_LIMIT_EXEMPT:
            return await call_next(request)

        key = self._client_key(request)
        now = time.monotonic()
        window = self._hits.setdefault(key, deque())

        while window and now - window[0] > 60:
            window.popleft()

        if len(window) >= self.limit:
            retry_after = max(1, int(60 - (now - window[0])))
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please slow down.",
                    "detail_bn": "অনেক বেশি অনুরোধ। একটু পরে আবার চেষ্টা করুন।",
                },
                headers={"Retry-After": str(retry_after)},
            )

        window.append(now)

        # Bound memory: drop clients that have gone quiet.
        if len(self._hits) > 10_000:
            for stale_key in [k for k, v in self._hits.items() if not v]:
                self._hits.pop(stale_key, None)

        return await call_next(request)
