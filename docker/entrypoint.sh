#!/usr/bin/env bash
# Container entrypoint.
#
# Applies migrations, ensures the AI artifacts exist, then starts the server.
# Everything here is idempotent so a restarted or rescheduled container
# converges on the same state rather than failing.

set -euo pipefail

cd /app

: "${DATABASE_URL:?DATABASE_URL must be set}"
: "${SECRET_KEY:?SECRET_KEY must be set}"

WORKERS="${WEB_CONCURRENCY:-4}"
BIND="${BIND:-0.0.0.0:8000}"

wait_for_database() {
  # Postgres may still be accepting connections when the app starts, so retry
  # rather than crash-looping the container.
  if [[ "${DATABASE_URL}" == sqlite* ]]; then
    return 0
  fi

  echo "Waiting for the database..."
  for _ in $(seq 1 30); do
    if python - <<'PY'
import os
import sys

from sqlalchemy import create_engine, text

try:
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
except Exception:
    sys.exit(1)
PY
    then
      echo "Database is ready."
      return 0
    fi
    sleep 2
  done

  echo "Database did not become ready in time." >&2
  return 1
}

apply_migrations() {
  echo "Applying migrations..."
  (cd backend && alembic upgrade head)
}

ensure_ai_artifacts() {
  # The AI endpoints return 503 without these. Building them at startup keeps
  # a fresh deployment fully functional without a separate manual step.
  if [[ -f backend/app/ai/artifacts/triage_model.joblib ]]; then
    echo "AI artifacts present."
    return 0
  fi

  if [[ "${SKIP_MODEL_BUILD:-false}" == "true" ]]; then
    echo "Skipping model build (SKIP_MODEL_BUILD=true)."
    return 0
  fi

  echo "Building datasets and training models (first run only)..."
  python ml/prepare_all.py
}

case "${1:-serve}" in
  serve)
    wait_for_database
    apply_migrations
    ensure_ai_artifacts

    if [[ "${SEED_ON_START:-false}" == "true" ]]; then
      echo "Seeding reference data..."
      python scripts/seed_database.py || echo "Seeding skipped or already applied."
    fi

    echo "Starting SasthoSetu on ${BIND} with ${WORKERS} workers."
    exec gunicorn app.main:app \
      --chdir backend \
      --worker-class uvicorn.workers.UvicornWorker \
      --workers "${WORKERS}" \
      --bind "${BIND}" \
      --timeout 60 \
      --graceful-timeout 30 \
      --access-logfile - \
      --error-logfile -
    ;;

  migrate)
    wait_for_database
    apply_migrations
    ;;

  seed)
    wait_for_database
    apply_migrations
    python scripts/seed_database.py
    ;;

  train)
    python ml/prepare_all.py
    ;;

  test)
    cd backend && APP_ENV=test python -m unittest discover -s tests -v
    ;;

  shell)
    exec /bin/bash
    ;;

  *)
    exec "$@"
    ;;
esac
