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
COPY --chown=sasthosetu:sasthosetu docker/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod +x /usr/local/bin/entrypoint.sh \
    && mkdir -p /app/data /app/backend/app/ai/artifacts \
    && chown -R sasthosetu:sasthosetu /app/data /app/backend/app/ai/artifacts

# Runs unprivileged: a container compromise should not also be root.
USER sasthosetu

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["serve"]
