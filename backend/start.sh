#!/bin/sh
# Render free plan has no background workers: run the Arq worker next to the API in one container.
set -e
alembic upgrade head
arq app.workers.main.WorkerSettings &
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
