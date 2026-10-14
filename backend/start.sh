#!/bin/sh
# Render free plan has no background workers: run the Arq worker next to the API in one container.
set -e
echo "start.sh: database host = $(python -c "from app.core.config import get_settings as s; from sqlalchemy.engine import make_url as u; print(u(s().database_url).host)")"
echo "start.sh: running migrations"
alembic upgrade head
echo "start.sh: starting worker and API on port ${PORT:-8000}"
arq app.workers.main.WorkerSettings &
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
