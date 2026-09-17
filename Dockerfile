# SasthoSetu application image.
#
# Built in two stages so the runtime image carries only the interpreter, the
# installed dependencies and the application - not the build toolchain used to
# compile them.

FROM python:3.13-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt \
    && /opt/venv/bin/pip install "uvicorn[standard]==0.49.0" "gunicorn==23.0.0"

# ---------------------------------------------------------------------------
# The triage and surge models and the seed data are committed, so the image
# only has to fall back to training when they are absent - which happens when
# .dockerignore excluded them, or on a checkout that predates them.
#
# Training here rather than at container start is deliberate: a first request
# that waits several minutes fails the health check on every managed host.
# Skipping it when the artifacts are already present keeps the build inside
# the time limit a free build machine allows.
#
# The imaging models are never built here. They need several GB of downloads;
# without them the skin and X-ray endpoints report themselves unavailable
# through their /status routes and nothing else is affected.

FROM builder AS models

WORKDIR /build

COPY ml ./ml
COPY backend ./backend
COPY data ./data

RUN if [ -f backend/app/ai/artifacts/triage_model.joblib ] \
      && [ -f backend/app/ai/artifacts/surge_model.joblib ]; then \
        echo "Trained models are present; skipping the training run."; \
    else \
        echo "No trained models found; building them."; \
        /opt/venv/bin/python ml/prepare_all.py; \
    fi

# ---------------------------------------------------------------------------

FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=production

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 sasthosetu

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

COPY --chown=sasthosetu:sasthosetu backend ./backend
COPY --chown=sasthosetu:sasthosetu ml ./ml
COPY --chown=sasthosetu:sasthosetu scripts ./scripts
COPY --chown=sasthosetu:sasthosetu frontend ./frontend
COPY --chown=sasthosetu:sasthosetu tools ./tools

# Trained models and the seed data they were derived from, seeding included.
COPY --from=models --chown=sasthosetu:sasthosetu \
     /build/backend/app/ai/artifacts ./backend/app/ai/artifacts
COPY --from=models --chown=sasthosetu:sasthosetu /build/data ./data
COPY --chown=sasthosetu:sasthosetu docker/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod +x /usr/local/bin/entrypoint.sh \
    && mkdir -p /app/data /app/backend/app/ai/artifacts \
    && chown -R sasthosetu:sasthosetu /app/data /app/backend/app/ai/artifacts

# Stamp the pages with the API address and write them to frontend/dist, which
# the application serves. A relative path is right here because the container
# answers both the pages and the API, so they share an origin whatever
# hostname the platform assigns.
RUN API_BASE_URL=/api/v1 python scripts/build_frontend.py \
    && chown -R sasthosetu:sasthosetu /app/frontend/dist

# Runs unprivileged: a container compromise should not also be root.
USER sasthosetu

EXPOSE 8000

# Follows the port the platform assigns. Hard-coding 8000 made the check fail
# forever anywhere PORT is injected, which is every managed host.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/health" || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["serve"]
