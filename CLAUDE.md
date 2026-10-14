# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

MeetMind AI is a Vietnamese meeting-intelligence MVP, built as a take-home project for a recruiter. It turns a meeting transcript into structured items (7 types) with the correct **final state**: if A was proposed and B was decided later, B is the decision and A is superseded. Every item carries verbatim evidence. A human reviews the items before publishing, and published meetings become an org-wide knowledge base for Q&A with citations.

- **Authoritative design:** `docs/superpowers/specs/2026-10-10-meetmind-mvp-design.md`.
- **Implementation plans:** `docs/superpowers/plans/`.
- **Assignment brief:** `MVP_Spec.md`.
- **README:** the root `README.md` is written for reviewers and is in Vietnamese.

## Working conventions (from the user)

- **Language.** The user writes in Vietnamese; reply in Vietnamese. UI strings, user-facing error messages and docs are Vietnamese. Code, identifiers and commit messages are English.
- **Commits and PRs carry only the user's identity.** No `Co-Authored-By: Claude` trailer and no "Generated with Claude Code" line. This overrides any default attribution.
- **Never run `ruff format`.** It rewrites many unrelated files. Use `ruff check` only.

## Commands

`make` is often missing on this Windows machine (Git Bash). Run the underlying commands from the `Makefile` directly when it is.

Infrastructure:
- `docker compose up -d db redis`: Postgres (`pgvector/pgvector:pg16`) and Redis.
- `docker/postgres-init/` creates `meeting_test` only on a fresh volume.
- `docker compose up -d --build`: the full stack (db, redis, backend, worker, frontend).
- `.env` lives at the repo root and is the single env source. Start from `.env.example`.

Backend (run from `backend/`, managed by uv):
- `uv run alembic upgrade head`: migrate.
- `uv run uvicorn app.main:app --reload --port 8000`: API. Routes live under `/api/v1`; health is `/api/v1/health`.
- `uv run arq app.workers.main.WorkerSettings`: worker.
- `REQUIRE_DB=1 uv run pytest -q`: full suite. Without `REQUIRE_DB=1`, DB tests skip when Postgres is down; with it, they fail instead.
- **Focusing a single test:** use `uv run pytest -q -k <name>`.
  - Always run pytest from `backend/`. Its config sets `testpaths = ../tests/backend` and `pythonpath = [".", ".."]`.
  - Passing explicit `../tests/...` paths breaks the asyncio config unless you also pass `-c pyproject.toml`.
- `uv run ruff check app ../tests ../evals && uv run mypy`: lint (mypy is strict over `app` and `../evals`).
- The DB test URL is `TEST_DATABASE_URL`, and the DB name **must** end in `_test`. Conftest refuses anything else because it drops and recreates the schema.

Frontend (run from `frontend/`, Next.js 15 App Router, React 19, Clerk, TanStack Query, Tailwind 4 + shadcn on `@base-ui/react`):
- `npm run dev`, `npm run build`, `npm run lint`, `npm run typecheck`, `npm test` (Vitest).
- `npx vitest run -t "<name>"`: single test.
- `npm run gen:types`: regenerates `openapi.json` and `src/types/api.ts` from `backend/scripts/export_openapi.py`.
  - Run it after any backend schema change.
  - CI fails on drift.
- `npx playwright test` (`make e2e`): end-to-end tests.
  - The config is `frontend/playwright.config.ts`, and the tests live in `tests/e2e/`.
  - The suite needs Clerk keys and a test user. Without them it skips.
  - It starts its own backend and worker with `LLM_PROVIDER=fake EMBEDDING_PROVIDER=hash`.

Evals (call the real LLM configured by `LLM_PROVIDER`/`LLM_MODEL_*`, so they need that provider's key):
- `cd backend && PYTHONPATH=.. uv run python -m evals.runners.run_pipeline`. Options: `--only <name>`, `--kind trap|realistic`.
- `... -m evals.runners.run_qa` also needs Postgres via `TEST_DATABASE_URL`.
- Thresholds live in `evals/config.yaml`. The runners exit 1 below threshold.
- Golden files in `evals/golden/` need human confirmation.
- Reports go to the gitignored `evals/reports/`; copy a run worth keeping to `evals/results/`. `docs/test-cases.md` is the Mission 2 write-up of the 14/10/2026 run.

## Architecture

**Layout.** Tests live outside the packages:
- `tests/backend/{unit,integration,api,db}`, `tests/frontend`, `tests/e2e`, and `tests/fixtures`. The fixtures include FakeLLM responses under `tests/fixtures/llm/payment_v2/`.
- Shared pytest helpers are imported as `tests.backend.<module>`, e.g. `pipeline_helpers` and `auth_helpers`. There are no `__init__.py` files.
- Vitest includes `../tests/frontend/**`.

**Backend layering** (`backend/app`): `api/v1/endpoints` → `services` → `repositories` → `models` (SQLAlchemy 2 async).
- Dependencies are in `api/deps.py`: `SessionDep`, `PrincipalDep`, `QueueDep`, `get_llm`, `get_embedder`.
- Errors use the envelope `{"error": {"code", "message"}}`, produced in `core/errors.py`. A catch-all middleware returns 500 `internal_error`.

**Auth and org isolation.**
- `core/auth.py` verifies Clerk JWTs: RS256 via a throttled JWKS cache, issuer and `azp` checks, and an org id taken from `o.id` (v2) or `org_id` (v1).
- Every root-table repository function takes `org_id`. Cross-org access returns **404**, never 403.
- `tests/backend/api/test_org_isolation.py` must cover any new endpoint.

**AI core** (`backend/app/ai`) has no dependency on the web layer.
- `pipeline.py` is a LangGraph graph: parse transcript → chunk/normalize → `extract` dialogue acts (LLM, parallel per chunk) → `check_quotes` (verbatim evidence, one retry) → `topics` (LLM) → **deterministic state machine** `domain/state_machine.py` → `arbitrate` (LLM, only on ambiguity signals) → `build_items` → `validate`.
- Final decisions come from the state machine, not the LLM. Only an explicit `DECIDE` act creates a decision.
- Prompts are versioned files `ai/prompts/<agent>/<version>.md`, selected by `PROMPT_VERSION`.
- LLM clients:
  - `ai/llm/client.py` (Anthropic) is the default production client.
  - `ai/llm/openai_client.py` (`OpenAILLM`, `LLM_PROVIDER=openai`) uses strict JSON-schema output; `strict_json_schema` drops pydantic defaults, which strict mode rejects.
  - `ai/llm/fake.py` (`FakeLLM`, queue-based) is used in tests.
  - `ai/llm/fixture.py` (`FixtureLLM`) reads `<dir>/<agent>.json`.
  - `core/llm.py::build_llm(settings)` picks one of these for both the API and the worker.

**Async jobs.** The Arq worker in `workers/main.py` runs four job types:
- `transcribe`: audio upload → OpenAI diarized STT (`ai/stt/`, `services/transcription.py`). The audio in `source_bytes` is replaced by a generated `[hh:mm:ss.mmm] Người nói A: …` `.txt`; status goes `transcribing` → `awaiting_speakers`. `POST /meetings/{id}/speakers` renames the labels, sets participants and starts `analyze` (`services/speakers.py`).
- `analyze`: transcript → review items.
- `index`: enqueued on publish; embeds approved items and transcript chunks.
- `notify`: enqueued on publish only when the org has a Discord webhook; best-effort, no `jobs` row.

**Discord** (`notify/`, `services/notifications.py`): per-org webhook in `org_settings` (`/settings/discord`, URL never returned, only Discord webhook hosts accepted). The daily digest is `POST /internal/digest` guarded by `X-Cron-Secret` = `CRON_SECRET`, called by `.github/workflows/digest.yml` at 01:00 UTC.

Job rules:
- Only `queued` jobs run.
- Progress is written in short sessions.
- A cancel marks the job failed.
- `jobs.active_for_meeting` and `jobs.latest_for_meeting` default to `kind="analyze"`.

**Review → publish.** Publish requires zero pending items (409 `pending_items`). Editing or rejecting an item clears its index, and republishing re-embeds the items whose `search_text` changed.

**Q&A** (`services/qa.py`, `repositories/search.py`, `ai/agents/qa.py`):
1. LLM filter extraction.
2. Hybrid search: pgvector cosine plus pg_trgm `word_similarity > 0.2`, over items and chunks, fused with RRF (k=60, top 12). Only published meetings in the caller's org are searched.
3. Supersession expansion marks contexts as "mới nhất" or "đã bị thay thế".
4. Answer generation, followed by a `check_citations` post-check.

Fallbacks and errors:
- Questions with no usable context get the fixed refusal: "Không đủ thông tin trong các cuộc họp đã phát hành."
- LLM and embedder failures return 503.
- Embeddings come from `EMBEDDING_PROVIDER=local` (bge-m3, 1024-dim, about 2 GB download), `gemini` (`gemini-embedding-001` requested at 1024 dims and L2-normalised, needs `GEMINI_API_KEY`) or `hash` (tests and e2e). The DB columns are fixed at `vector(1024)`; `core/embedding.py::build_embedder(settings)` picks the embedder. Compose build arg `INSTALL_EMBEDDINGS=false` drops torch from the image.

**Frontend** (`frontend/src`):
- `app/` holds the routes: `/`, `/meetings/new`, `/meetings/[id]/review`, `/meetings/[id]/minutes`, `/qa`, `/settings` (Discord), `/select-org`, and sign-in/up.
- `features/<area>/` holds UI and hooks.
- `lib/api-client.ts` and `lib/use-api.ts` attach the Clerk token.
- `middleware.ts` enforces sign-in and redirects users without an active org to `/select-org`.
- On an org switch, the query cache is cleared and the subtree is re-mounted with a key.

**CI.**
- `.github/workflows/ci.yml` has three jobs:
  - backend: ruff, mypy, pytest against a pgvector service.
  - frontend: lint, typecheck, Vitest, build, OpenAPI drift check.
  - e2e: skips without Clerk secrets.
- `eval.yml` runs the evals on PRs that touch `backend/app/ai/prompts/**`, `backend/app/ai/agents/**` or `evals/**`. It skips without `ANTHROPIC_API_KEY`.
