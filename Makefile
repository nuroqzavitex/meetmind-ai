.PHONY: up down db migrate api worker test lint

up:
	docker compose up -d --build

down:
	docker compose down

db:
	docker compose up -d db redis

migrate:
	cd backend && uv run alembic upgrade head

api:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

worker:
	cd backend && uv run arq app.workers.main.WorkerSettings

test:
	cd backend && REQUIRE_DB=1 uv run pytest

lint:
	cd backend && uv run ruff check app ../tests ../evals && uv run mypy
