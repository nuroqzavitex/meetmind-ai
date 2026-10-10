# Plan 2 — Backend, Clerk auth & API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap the finished AI core (`app/ai/`) in a FastAPI service with Clerk JWT auth, org-scoped Postgres storage, an Arq worker that runs `analyze_transcript`, and the review → publish → export → report/reopen API of spec §12.1 (everything except `/qa`).

**Architecture:** `endpoints → services → repositories / ai` (spec §4). Every repository function on a root table takes `org_id` as a required parameter; child tables are reached only through a meeting already checked against the org. Uploads are parsed synchronously (422 on bad files), stored on the meeting, and analysed by an Arq job that writes progress into `jobs`. The queue and the LLM are injected so tests run with a fake queue and `FakeLLM`.

**Tech Stack:** FastAPI, Pydantic v2 + pydantic-settings, SQLAlchemy 2.0 async + asyncpg, Alembic, PostgreSQL 16 (pgvector image) , Arq + Redis, PyJWT[crypto], httpx (tests + JWKS fetch), pytest.

**Spec:** `docs/superpowers/specs/2026-10-10-meetmind-mvp-design.md` (v3) — §4, §5, §7.2, §8.1 (job/progress/error), §10.5, §12.1, §13.1, §14. Plan 1 (`2026-10-10-plan-1-ai-core.md`) built `app/ai/`; do not change its behaviour.

## Global Constraints

- Python ≥ 3.11, managed with `uv` in `backend/`; ruff (line length 100) and `mypy --strict` stay clean; `files` in mypy config already covers `app` and `../evals`.
- Tests live in `tests/backend/{unit,integration,db,api}`; focused runs: `cd backend && uv run pytest -c pyproject.toml ../tests/backend/<path>`. Tests never call a real LLM or real Clerk.
- Dependency rule: endpoints never import `app.ai.agents` or repositories directly — only services; `app/ai/` never imports from `app.api`, `app.services`, `app.repositories`, `app.models` or `app.core.auth`.
- Every repository function on `meetings`, `jobs`, `items` takes `org_id: str` (keyword) and filters by it. Cross-org access returns **404**, never 403.
- Error body for every non-2xx response: `{"error": {"code": "<snake_case>", "message": "<text>"}}`. Status codes: 401 (no/bad token), 403 (no active org), 404, 409 (state conflict), 413 (file too large), 422 (validation / unparseable transcript).
- No `users` table. `item_events` stores `actor_id` + `actor_name` copied from the principal.
- Meeting status: `draft | analyzing | in_review | published | failed`. Job status: `queued | running | succeeded | failed`. Job kind: `analyze` (`index` arrives in Plan 4). Item event action: `created | approved | edited | rejected | reported | reopened`.
- Ids: meetings and jobs use `str(uuid4())`; item ids are the pipeline's `f"{meeting_id}-i{n:03d}"` (globally unique because meeting ids are). Use `String` PK columns.
- Settings come from env / `.env` (repo root) via pydantic-settings; nothing reads `os.environ` directly except Settings.
- Commits: conventional messages, **no `Co-Authored-By` trailer and no "Generated with" line** — the author identity is the user's alone.

## Review Focus

1. Garbage, empty, non-UTF-8 or oversized uploads → 422/413 with the error envelope, never 500 and never a half-created meeting. (Task 5 tests.)
2. The analyze job fails mid-way (LLMError / AnalysisError) → job `failed` with a readable `error` and `step`, meeting `failed`; `reanalyze` then succeeds without duplicating utterances, acts, topics or items. (Task 6 tests.)
3. Clerk tokens in both org-claim formats (v2 `o.id`, v1 `org_id`), wrong `azp`, wrong `iss`, expired, unknown `kid` that appears after a JWKS refresh. (Task 3 tests.)
4. Editing/approving an item of a meeting that is `published` (without reopen) or `analyzing` → 409; publishing while items are still `pending` or a job is running → 409. (Tasks 7–8 tests.)
5. A user of org X hitting every id-taking endpoint with org Y's ids → 404 and org Y's data unchanged. (Task 9 test.)

---

### Task 1: Service skeleton — settings, app factory, error envelope, health

**Files:**
- Modify: `backend/pyproject.toml` (deps: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]>=2.0`, `asyncpg`, `alembic`, `pydantic-settings`, `pyjwt[crypto]`, `arq`, `httpx`, `python-multipart`; pytest option `asyncio_default_fixture_loop_scope = "function"`)
- Create: `backend/app/core/__init__.py`, `backend/app/core/config.py`, `backend/app/core/errors.py`, `backend/app/main.py`, `backend/app/api/__init__.py`, `backend/app/api/v1/__init__.py`, `backend/app/api/v1/router.py`, `backend/app/api/v1/endpoints/__init__.py`, `backend/app/api/v1/endpoints/health.py`
- Test: `tests/backend/api/test_health_errors.py`, `tests/backend/unit/test_settings.py`

**Interfaces:**
- Produces:
  - `class Settings(BaseSettings)` in `app/core/config.py`, `model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")`, fields: `database_url: str = "postgresql+asyncpg://app:app@localhost:5432/meeting"`, `redis_url: str = "redis://localhost:6379"`, `clerk_jwks_url: str = ""`, `clerk_issuer: str = ""`, `clerk_authorized_parties: list[str] = ["http://localhost:3000"]` (accepts a comma-separated env string), `anthropic_api_key: SecretStr | None = None`, `llm_model_default: str = "claude-sonnet-5-5"`, `llm_model_arbitrate: str = "claude-opus-5-5"`, `prompt_version: str = "v1"`, `max_upload_bytes: int = 5_000_000`, `cors_origins: list[str] = ["http://localhost:3000"]`; method `ai_settings() -> AISettings` mapping models/prompt_version; `get_settings() -> Settings` (lru_cache).
  - `class AppError(Exception)` with `status: int`, `code: str`, `message: str`; subclasses `NotFound(code="not_found")`, `Conflict(code)`, `Unprocessable(code)`, `PayloadTooLarge(code="file_too_large")`, `Unauthorized(code="unauthorized")`, `Forbidden(code="no_active_org")` — each takes `message` (and `code` where listed without a default).
  - `def install_error_handlers(app: FastAPI) -> None` — maps `AppError`, `StarletteHTTPException` and `RequestValidationError` (→ 422, code `validation_error`) to the envelope.
  - `def create_app(settings: Settings | None = None) -> FastAPI` in `app/main.py`; module-level `app = create_app()`; CORS from `settings.cors_origins`; router mounted at `/api/v1`; `app.state.settings` holds the settings.
  - `GET /api/v1/health` → `{"status": "ok"}` (no auth).

- [ ] **Step 1: Write the failing tests**

```python
# tests/backend/api/test_health_errors.py
from fastapi.testclient import TestClient
from app.core.errors import NotFound
from app.main import create_app

def test_health_ok():
    r = TestClient(create_app()).get("/api/v1/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}

def test_unknown_route_uses_error_envelope():
    r = TestClient(create_app()).get("/api/v1/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"

def test_app_error_envelope():
    app = create_app()
    @app.get("/boom")
    def boom() -> None:
        raise NotFound("Không tìm thấy cuộc họp")
    r = TestClient(app).get("/boom")
    assert r.status_code == 404
    assert r.json() == {"error": {"code": "not_found", "message": "Không tìm thấy cuộc họp"}}

# tests/backend/unit/test_settings.py
def test_authorized_parties_from_comma_string(monkeypatch):
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", "http://a.test,http://b.test")
    from app.core.config import Settings
    assert Settings(_env_file=None).clerk_authorized_parties == ["http://a.test", "http://b.test"]

def test_ai_settings_mapping():
    from app.core.config import Settings
    s = Settings(_env_file=None, llm_model_arbitrate="m-arb", prompt_version="v9")
    ai = s.ai_settings()
    assert ai.model_for("arbitrate") == "m-arb" and ai.prompt_version == "v9"
```

- [ ] **Step 2:** Run `uv run pytest -c pyproject.toml ../tests/backend/api/test_health_errors.py ../tests/backend/unit/test_settings.py` → FAIL (modules missing).
- [ ] **Step 3:** Add deps (`uv add ...`), implement the files above. For the comma list use a `field_validator(mode="before")` that splits strings and annotate the field with `NoDecode` (pydantic-settings ≥ 2.7) so the env value is not JSON-decoded first.
- [ ] **Step 4:** Run the two test files → PASS; run the full suite, `uv run ruff check app ../tests ../evals`, `uv run mypy` → clean.
- [ ] **Step 5:** Commit `feat(api): add FastAPI skeleton with settings and error envelope`.

---

### Task 2: Database — ORM models, Alembic migration, test-DB harness, compose

**Files:**
- Create: `backend/app/db/__init__.py`, `backend/app/db/base.py`, `backend/app/db/session.py`, `backend/app/models/__init__.py`, `backend/app/models/meeting.py`, `backend/app/models/item.py`, `backend/app/models/job.py`
- Create: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/alembic/versions/0001_initial.py`
- Create: `docker-compose.yml` (services `db` and `redis` now; Task 10 adds `backend`/`worker`), `docker/postgres-init/01-test-db.sql` (`CREATE DATABASE meeting_test;`)
- Create: `tests/backend/conftest.py` (DB fixtures), `tests/backend/db/test_migrations.py` (test dirs have no `__init__.py`, matching the existing `tests/backend/unit`; shared helpers are imported as `tests.backend.<module>`)
- Modify: `backend/pyproject.toml` (pytest `markers = ["db: needs Postgres"]`)

**Interfaces:**
- Produces:
  - `class Base(DeclarativeBase)` in `app/db/base.py`.
  - `def make_engine(url: str) -> AsyncEngine`, `def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]` (`expire_on_commit=False`) in `app/db/session.py`; FastAPI dependency `async def get_session(request: Request) -> AsyncIterator[AsyncSession]` reading `request.app.state.sessionmaker` (created lazily in `create_app` from settings).
  - ORM classes (table names from spec §7.2), all timestamps `DateTime(timezone=True)` with server default `now()`:
    - `Meeting`: `id: str` PK, `org_id: str` (indexed with `meeting_date`), `created_by: str`, `title: str`, `meeting_date: date`, `project: str | None`, `organizer: str | None`, `context: dict` (JSONB — the full `MeetingContext` dump), `status: str` (default `"draft"`), `source_filename: str`, `source_bytes: bytes` (LargeBinary), `created_at`, `published_at: datetime | None`.
    - `Utterance`: `pk: int` autoincrement PK, `meeting_id` FK (cascade delete), `id: str` (e.g. `u0042`; unique with `meeting_id`), `seq: int`, `speaker`, `start: float`, `end: float | None`, `text`. Index `(meeting_id, seq)`.
    - `DialogueActRow` (table `dialogue_acts`): `pk` PK, `meeting_id` FK cascade, `id: str`, `utterance_id: str`, `act: str`, `option: str | None`, `topic_id: str | None`, `payload: dict` (JSONB, full `DialogueAct` dump).
    - `TopicRow` (table `topics`): `pk` PK, `meeting_id` FK cascade, `topic_id: str`, `question: str`, `history: dict` (JSONB, full `Topic` dump), `ambiguous_decides: list` (JSONB).
    - `Item` (table `items`): `id: str` PK, `org_id: str` indexed, `meeting_id` FK cascade (indexed), `type: str`, `status: str`, `review_state: str`, `data: dict` (JSONB, full `MeetingItem` dump — the source of truth for item fields), `position: int` (pipeline order), `created_at`, `updated_at`.
    - `ItemEvent` (table `item_events`): `pk` PK, `item_id` FK cascade, `actor_id: str`, `actor_name: str`, `action: str`, `before: dict | None`, `after: dict | None`, `reason: str | None`, `created_at`.
    - `Job`: `id: str` PK, `org_id: str` indexed, `kind: str`, `meeting_id` FK cascade, `status: str` default `"queued"`, `step: str | None`, `progress: float` default 0, `error: str | None`, `result: dict | None`, `created_at`, `updated_at`.
  - Migration `0001_initial`: `CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;` then all tables above. (`search_text`, `embedding`, `indexed_at`, `transcript_chunks` arrive with Plan 4.)
  - `alembic/env.py` runs async (`async_engine_from_config`), reads the URL from `Settings().database_url` unless `-x url=` or `config.attributes["url"]` is given, `target_metadata = Base.metadata`.
  - Test harness in `tests/backend/conftest.py` (so both `db/` and `api/` tests see the fixtures):
    - `TEST_DATABASE_URL` env, default `postgresql+asyncpg://app:app@localhost:5432/meeting_test`.
    - session-scoped **sync** fixture `migrated_db_url`: if the server is unreachable → `pytest.skip("Postgres not reachable — run `docker compose up -d db`")` unless env `REQUIRE_DB=1` (then fail); otherwise drop all tables + `alembic_version`, run `alembic upgrade head` programmatically, yield the URL.
    - function-scoped async fixture `sessionmaker` (`async_sessionmaker[AsyncSession]`): new engine with `NullPool` on `migrated_db_url`, `TRUNCATE ... RESTART IDENTITY CASCADE` on every table before yielding, disposes after.
    - every test that uses these is marked `pytest.mark.db`.

- [ ] **Step 1: Write the failing tests** (`tests/backend/db/test_migrations.py`, marked `db`):
  - `test_upgrade_creates_tables_and_extensions` — after `migrated_db_url`, `SELECT extname FROM pg_extension` contains `vector` and `pg_trgm`; `information_schema.tables` contains the 7 tables.
  - `test_models_match_migration` — run alembic's `compare_metadata(MigrationContext.configure(conn), Base.metadata)` inside `conn.run_sync` → `== []`.
  - `test_meeting_cascade_delete` — insert a `Meeting` with one `Utterance`, one `Item`, one `ItemEvent`, one `Job`; delete the meeting; all child counts are 0.
- [ ] **Step 2:** Start Postgres: `docker compose up -d db` (the init script creates `meeting_test` on first start). Run `uv run pytest -c pyproject.toml ../tests/backend/db -v` → FAIL (imports missing). With Docker down the tests must SKIP, not error — check that too.
- [ ] **Step 3:** Implement models, session helpers, alembic files, the migration, compose (`pgvector/pgvector:pg16` with the init-script volume `./docker/postgres-init:/docker-entrypoint-initdb.d:ro`, `redis:7`, ports 5432/6379, volume `pgdata`).
- [ ] **Step 4:** Tests PASS; full suite, ruff, mypy clean.
- [ ] **Step 5:** Commit `feat(db): add ORM models, initial migration and Postgres test harness`.

---

### Task 3: Clerk authentication — `get_principal`

**Files:**
- Create: `backend/app/core/auth.py`
- Create: `tests/backend/auth_helpers.py` (test RSA key, JWKS dict, `make_token(**claims)`; reused by API tests)
- Test: `tests/backend/unit/test_auth.py`

**Interfaces:**
- Produces:
  - `class Principal(BaseModel)`: `user_id: str`, `org_id: str`, `name: str`.
  - `class JWKSCache`: `__init__(self, fetch: Callable[[], Awaitable[dict[str, Any]]])`; `async def key_for(self, kid: str) -> Any` — returns the cached public key; on an unknown `kid` refetches once (at most one refetch per 60 s to avoid hammering), still unknown → `Unauthorized`.
  - `def http_jwks_fetcher(url: str) -> Callable[[], Awaitable[dict[str, Any]]]` (httpx.AsyncClient GET, 5 s timeout).
  - `async def verify_token(token: str, *, jwks: JWKSCache, issuer: str, authorized_parties: list[str], leeway: int = 5) -> Principal` — RS256 only; requires `exp`, `nbf`, `iss`, `sub`; `iss` must equal `issuer`; `azp`, when present, must be in `authorized_parties`; org id = `claims["o"]["id"]` (v2) else `claims["org_id"]` (v1); missing org → `Forbidden`; name = `claims.get("name") or sub`. Any PyJWT error → `Unauthorized`.
  - FastAPI dependency `async def get_principal(request: Request) -> Principal` — reads `Authorization: Bearer <token>` (missing/malformed → `Unauthorized`), uses `request.app.state.jwks` (a `JWKSCache` created in `create_app` from `settings.clerk_jwks_url`) and settings. Tests swap `app.state.jwks` for one built from the test JWKS.

- [ ] **Step 1: Write the failing tests** (`tests/backend/unit/test_auth.py`; use `auth_helpers.make_token`, issuer `https://clerk.test`, party `http://localhost:3000`):
  - `test_v2_org_claim` — claims `{"o": {"id": "org_a", "rol": "admin"}}` → `Principal(org_id="org_a")`.
  - `test_v1_org_claim` — `{"org_id": "org_b"}` → `org_id == "org_b"`.
  - `test_name_claim_and_fallback` — with `name="Lan"` → `"Lan"`; without → equals `sub`.
  - `test_no_org_is_forbidden` → raises `Forbidden`.
  - parametrized `test_rejected_tokens` → `Unauthorized` for: expired `exp`, future `nbf`, wrong `iss`, `azp="http://evil.test"`, HS256-signed token, token signed by a different RSA key with the same `kid`, garbage string.
  - `test_unknown_kid_triggers_one_refetch` — fetcher returns JWKS without the key first, with it second; verify succeeds and the fetcher was called twice; a second unknown kid within 60 s → `Unauthorized` without a third call.
  - `test_dependency_missing_header_401` — tiny FastAPI app with a route depending on `get_principal`; no header → 401 envelope `unauthorized`; `Bearer` + token without org → 403 `no_active_org`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement with `jwt.decode(token, key, algorithms=["RS256"], issuer=issuer, leeway=leeway, options={"require": ["exp", "nbf", "iss", "sub"]})`; read the header `kid` via `jwt.get_unverified_header`; build keys with `jwt.PyJWK(jwk_dict).key`.
- [ ] **Step 4:** PASS; full suite, ruff, mypy clean.
- [ ] **Step 5:** Commit `feat(auth): verify Clerk session JWTs and resolve the active org`.

---

### Task 4: Org-scoped repositories

**Files:**
- Create: `backend/app/repositories/__init__.py`, `backend/app/repositories/meetings.py`, `backend/app/repositories/jobs.py`, `backend/app/repositories/items.py`
- Test: `tests/backend/db/test_repositories.py`

**Interfaces:**
- Consumes: ORM models (Task 2); domain models `Utterance`, `DialogueAct`, `MeetingItem`, `Topic` from `app.ai`.
- Produces (all `async`, first parameter `session: AsyncSession`, everything else keyword-only; no commits inside repositories — services commit):
  - `meetings.py`: `create(session, *, org_id, created_by, ctx: MeetingContext, filename: str, data: bytes) -> Meeting` (id = `ctx.meeting_id`, status `"draft"`); `get(session, *, org_id, meeting_id) -> Meeting | None`; `list_(session, *, org_id, project: str | None = None, status: str | None = None) -> list[Meeting]` (newest `meeting_date` first, then `created_at` desc); `set_status(session, *, org_id, meeting_id, status: str, published_at: datetime | None = None) -> None`; `replace_analysis(session, *, org_id, meeting_id, utterances: list[Utterance], acts: list[DialogueAct], topics: list[Topic]) -> None` (deletes existing children of those three tables first); `get_utterances(session, *, org_id, meeting_id) -> list[Utterance]` (by seq); `get_topics(session, *, org_id, meeting_id) -> list[Topic]`. Child accessors return `[]` when the meeting is not in the org.
  - `jobs.py`: `create(session, *, org_id, meeting_id, kind: str) -> Job`; `get(session, *, org_id, job_id) -> Job | None`; `update(session, *, org_id, job_id, **fields: Any) -> None`; `active_for_meeting(session, *, org_id, meeting_id) -> Job | None` (status `queued`/`running`).
  - `items.py`: `replace_for_meeting(session, *, org_id, meeting_id, items: list[MeetingItem]) -> list[Item]` (deletes existing items of the meeting, inserts with `position` = list index, `data = item.model_dump(mode="json")`); `list_for_meeting(session, *, org_id, meeting_id) -> list[Item]` (by position); `get(session, *, org_id, item_id) -> Item | None`; `save(session, *, item: Item, model: MeetingItem) -> None` (writes `data`, `type`, `status`, `review_state` from the model); `add_event(session, *, item: Item, actor: Principal, action: str, before: dict | None = None, after: dict | None = None, reason: str | None = None) -> ItemEvent`; `events(session, *, org_id, item_id) -> list[ItemEvent]`; helper `to_model(item: Item) -> MeetingItem`.

- [ ] **Step 1: Write the failing tests** (marked `db`):
  - `test_meeting_roundtrip_and_list_filters` — create two meetings in `org_a` (projects `pay`, `crm`) and one in `org_b`; `list_(org_id="org_a")` returns the two, newest date first; `project="pay"` returns one; `status="draft"` returns both.
  - `test_cross_org_get_returns_none` — for meetings, jobs and items: `get` with the other org → `None`; `get_utterances` / `get_topics` with the other org → `[]`.
  - `test_replace_analysis_is_idempotent` — call `replace_analysis` twice with the same 3 utterances → 3 rows, not 6; same for `items.replace_for_meeting`.
  - `test_item_model_roundtrip` — a `MeetingItem` with `due_date=date(2026,10,16)` and evidence survives `replace_for_meeting` → `to_model` equal to the original.
  - `test_active_job` — queued job is active; after `update(status="succeeded")` → `None`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS; suite/ruff/mypy clean.
- [ ] **Step 5:** Commit `feat(repo): add org-scoped repositories for meetings, jobs and items`.

---

### Task 5: Upload & read API — meetings, jobs, queue abstraction

**Files:**
- Create: `backend/app/schemas/__init__.py`, `backend/app/schemas/meetings.py`, `backend/app/schemas/jobs.py`
- Create: `backend/app/services/__init__.py`, `backend/app/services/meetings.py`
- Create: `backend/app/workers/__init__.py`, `backend/app/workers/queue.py`
- Create: `backend/app/api/deps.py`, `backend/app/api/v1/endpoints/meetings.py`, `backend/app/api/v1/endpoints/jobs.py`
- Create: `tests/backend/api/conftest.py` (fixtures below)
- Test: `tests/backend/api/test_meetings_api.py`

**Interfaces:**
- Consumes: `parse_transcript(filename, data)` and `TranscriptParseError` from `app.ai`; repositories (Task 4); `get_principal` (Task 3).
- Produces:
  - `class JobQueue(Protocol)`: `async def enqueue(self, kind: str, *, org_id: str, meeting_id: str, job_id: str) -> None`. `class ArqQueue` (wraps an `arq` `ArqRedis` pool created lazily from `settings.redis_url`; `enqueue_job(kind, org_id=..., meeting_id=..., job_id=..., _job_id=job_id)`). Dependency `get_queue(request) -> JobQueue` reads `request.app.state.queue`.
  - Schemas: `MeetingContextIn` (`title: str` 1–200 chars, `meeting_date: date`, `project`, `organizer`, `participants: list[Participant] = []`, `glossary: list[str] = []`); `MeetingCreated` (`meeting_id`, `job_id`); `MeetingSummary` (`id, title, meeting_date, project, status, created_at, published_at`); `MeetingDetail` (`MeetingSummary` fields + `context: MeetingContext`, `utterances: list[Utterance]`, `active_job_id: str | None`); `JobOut` (`id, kind, meeting_id, status, step, progress, error`).
  - `services/meetings.py`: `async def create_meeting(session, queue, *, principal, ctx_in: MeetingContextIn, filename: str, data: bytes, max_bytes: int) -> MeetingCreated` — size check (`PayloadTooLarge`), empty file or `TranscriptParseError` → `Unprocessable("transcript_parse_error", <parser message>)`, zero utterances → same; then create meeting (status `analyzing`) + job (`analyze`), **commit, then enqueue**. `list_meetings`, `get_meeting` (→ `NotFound`), `get_job` (→ `NotFound`), `reanalyze(session, queue, *, principal, meeting_id) -> MeetingCreated` (only when status `failed`, else `Conflict("not_failed")`; sets `analyzing`, new job, commit, enqueue).
  - Endpoints: `POST /meetings` (multipart `file: UploadFile`, `context: str` JSON → validated as `MeetingContextIn`; bad JSON → 422 `validation_error`; returns 201 `MeetingCreated`), `GET /meetings?project=&status=` → `list[MeetingSummary]`, `GET /meetings/{id}` → `MeetingDetail`, `POST /meetings/{id}/reanalyze` → 202 `MeetingCreated`, `GET /jobs/{id}` → `JobOut`.
  - Test fixtures in `tests/backend/api/conftest.py`: `class FakeQueue` (records `(kind, org_id, meeting_id, job_id)` in `.calls`); fixture `client` → `httpx.AsyncClient(transport=ASGITransport(app))` for an app built by `create_app(Settings(_env_file=None, database_url=<test url>, clerk_issuer="https://clerk.test"))` with `app.state.sessionmaker` = the test sessionmaker, `app.state.queue = FakeQueue()`, `app.state.jwks` = test JWKS cache; helper `auth(org="org_a", user="user_1", name="Lan") -> dict[str, str]` header factory.

- [ ] **Step 1: Write the failing tests** (marked `db`), using `tests/fixtures/transcripts/payment_v2.txt`:
  - `test_upload_creates_meeting_and_enqueues` — 201; body has both ids; `FakeQueue.calls == [("analyze", "org_a", meeting_id, job_id)]`; `GET /jobs/{job_id}` → `status == "queued"`; `GET /meetings/{id}` → status `analyzing`, `active_job_id == job_id`, `utterances == []`.
  - parametrized `test_bad_uploads_rejected` → expected status + code, and `GET /meetings` stays empty and no enqueue: empty file (422 `transcript_parse_error`), `b"\xff\xfe\x00garbage"` named `x.txt` (422), `notes.pdf` (422), bytes longer than `max_upload_bytes` (413 `file_too_large`), `context="{not json"` (422 `validation_error`), context missing `title` (422).
  - `test_requires_auth_and_org` — no header → 401; token without org → 403.
  - `test_list_filters_by_project` — two uploads with projects `pay`/`crm`; `?project=pay` → 1.
  - `test_reanalyze_only_when_failed` — fresh meeting → 409 `not_failed`; set status `failed` via repository → 202, a second enqueue recorded, new job id.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS; suite/ruff/mypy clean.
- [ ] **Step 5:** Commit `feat(api): upload transcripts, read meetings and poll jobs`.

---

### Task 6: Arq worker — the `analyze` job

**Files:**
- Create: `backend/app/services/analysis.py`, `backend/app/workers/main.py`, `backend/app/ai/llm/factory.py`
- Test: `tests/backend/db/test_analysis_job.py`

**Interfaces:**
- Consumes: `analyze_transcript(*, ctx, filename, data, llm, settings, on_progress)` → `AnalysisResult(utterances, acts, topics, specs, items)`; `AnalysisError.step`; repositories.
- Produces:
  - `def make_llm(settings: Settings) -> LLMClient` in `app/ai/llm/factory.py` — `AnthropicLLM(settings.ai_settings(), anthropic.AsyncAnthropic(api_key=<secret or None>, max_retries=4))`. (It may import `app.core.config.Settings` only under `TYPE_CHECKING`; take the two values it needs as parameters if that keeps `app/ai` free of `app.core` — preferred signature: `make_llm(ai: AISettings, api_key: str | None) -> LLMClient`.)
  - `async def run_analysis(sm: async_sessionmaker[AsyncSession], llm: LLMClient, ai: AISettings, *, org_id: str, meeting_id: str, job_id: str) -> None` in `services/analysis.py`:
    1. load meeting + job (missing → log and return); job `running`, step `start`, progress 0; commit.
    2. `on_progress(step, value)` writes `step`/`progress` in its **own short session + commit** (so polling sees it).
    3. run `analyze_transcript(ctx=MeetingContext(**meeting.context), filename=meeting.source_filename, data=meeting.source_bytes, ...)`.
    4. success: in one transaction `replace_analysis`, `items.replace_for_meeting`, one `created` event per item (actor `system` / `MeetMind AI`), meeting `in_review`, job `succeeded`, progress 1.0, `result = {"items": n}`.
    5. failure: `AnalysisError` → job `failed`, `step = e.step`, `error = f"Bước {e.step} lỗi: {e}"`; `TranscriptParseError` → `error = f"Không đọc được transcript: {e}"`; any other exception → `error = "Lỗi không mong muốn khi phân tích"` and log the traceback. Meeting `failed` in every case. Never re-raise (Arq must not retry a deterministic failure).
  - `app/workers/main.py`: `async def analyze(ctx: dict[str, Any], *, org_id: str, meeting_id: str, job_id: str) -> None` calling `run_analysis(ctx["sessionmaker"], ctx["llm"], ctx["ai"], ...)`; `startup(ctx)` builds settings, engine, sessionmaker, `make_llm`, `ai`; `shutdown(ctx)` disposes the engine; `class WorkerSettings` with `functions = [analyze]`, `on_startup`, `on_shutdown`, `redis_settings = RedisSettings.from_dsn(get_settings().redis_url)`, `max_tries = 1`, `job_timeout = 900`.

- [ ] **Step 1: Write the failing tests** (marked `db`; meetings created through the Task 4 repository with `payment_v2.txt` and the `CTX_PAYMENT` participants; LLM = `FakeLLM` built from `tests/fixtures/llm/payment_v2/*.json` exactly as `tests/backend/integration/test_pipeline_fake.py::fake_from_fixtures` does):
  - `test_analysis_persists_results` — after `run_analysis`: job `succeeded`, progress 1.0; meeting `in_review`; utterance count = 16; one `decision` item whose `data.content` contains `Postgres`; every item has exactly one `created` event; topics stored.
  - `test_progress_is_visible_during_run` — wrap the FakeLLM so the `topics` call reads the job row through a separate session and records `(step, progress)`; recorded step is `topics` (or later) with progress ≥ 0.5.
  - `test_llm_failure_marks_failed` — FakeLLM with no `topics` responses → job `failed`, `step == "topics"`, `error` starts with `"Bước topics lỗi"`; meeting `failed`; no items.
  - `test_reanalyze_after_failure_does_not_duplicate` — fail once, then run again with a good FakeLLM → item and utterance counts equal a single clean run.
  - `test_worker_function_delegates` — call `app.workers.main.analyze({"sessionmaker": sm, "llm": fake, "ai": AISettings()}, org_id=..., meeting_id=..., job_id=...)` → job `succeeded`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS; suite/ruff/mypy clean.
- [ ] **Step 5:** Commit `feat(worker): run the analysis pipeline as an Arq job with progress`.

---

### Task 7: Review API — items, topics, patch, approve-clean, events

**Files:**
- Create: `backend/app/schemas/items.py`, `backend/app/services/review.py`, `backend/app/api/v1/endpoints/items.py`
- Modify: `backend/app/api/v1/endpoints/meetings.py` (items/topics/approve-clean routes), `backend/app/api/v1/router.py`
- Test: `tests/backend/api/test_review_api.py`

**Interfaces:**
- Consumes: `REQUIRED_FLAGS` from `app/ai/agents/validate.py`; repositories; `Topic` model.
- Produces:
  - Schemas: `ItemOut` = `MeetingItem` fields (ids as strings) — define it as `class ItemOut(MeetingItem)` so the OpenAPI schema mirrors the domain model; `ItemPatch` (all optional: `content`, `status: ItemStatus`, `owner`, `requester`, `due_date`, `rationale`, `condition`; `extra="forbid"`); `ItemAction` (`action: Literal["approve", "edit", "reject"]`, `patch: ItemPatch | None = None`, `reason: str | None = None`); `ApproveCleanOut` (`approved: int`); `TopicOut` = `Topic` dump.
  - `services/review.py`:
    - `list_items(session, *, principal, meeting_id) -> list[MeetingItem]` — meeting must exist in org (`NotFound`); order: items with `low_confidence` first, then other flagged items, then clean ones; stable by `position` inside each group.
    - `list_topics(session, *, principal, meeting_id) -> list[Topic]`.
    - `act_on_item(session, *, principal, item_id, action: ItemAction) -> MeetingItem` — item not in org → `NotFound`; meeting status must be `in_review` (else `Conflict("not_in_review")`). `approve` → `review_state=approved`, event `approved`. `reject` → `rejected`, event `rejected`. `edit` → `patch` required (`Unprocessable("patch_required")`); for a `decision`, a patch that changes `content` or `status` requires a non-empty `reason` (`Unprocessable("reason_required")`); apply the patch, recompute the required-field flags for that type (drop that type's `REQUIRED_FLAGS` flags, re-add the ones still missing; other flags kept), `review_state=edited`, event `edited` with `before`/`after` = full item dumps and `reason`. Commit.
    - `approve_clean(session, *, principal, meeting_id) -> int` — meeting `in_review` else 409; every `pending` item with `flags == []` → `approved` + event; returns the count.
  - Endpoints: `GET /meetings/{id}/items` → `list[ItemOut]`, `GET /meetings/{id}/topics` → `list[TopicOut]`, `PATCH /items/{id}` (`ItemAction`) → `ItemOut`, `POST /meetings/{id}/items/approve-clean` → `ApproveCleanOut`, `GET /items/{id}/events` → `list[ItemEventOut]` (`action, actor_name, reason, created_at`).
  - Test helper (in `tests/backend/api/conftest.py`): `async def seed_analyzed_meeting(sessionmaker, org_id="org_a") -> str` — inserts a meeting in `in_review` with items built by running `analyze_transcript` on `payment_v2.txt` with the fixture FakeLLM (reuse `run_analysis`), returns the meeting id.

- [ ] **Step 1: Write the failing tests** (marked `db`):
  - `test_items_flagged_first` — every item before the first clean item has flags; any `low_confidence` items come before other flagged ones.
  - `test_approve_and_reject_record_events` — `PATCH approve` → `review_state == "approved"`; events endpoint shows `approved` with `actor_name == "Lan"`.
  - `test_edit_action_item_clears_satisfied_flag` — pick the staging action item (flag `missing_due_date`); patch `due_date="2026-10-20"` → flags no longer contain `missing_due_date`; `review_state == "edited"`; event has `before.due_date is None` and `after.due_date == "2026-10-20"`.
  - `test_decision_change_needs_reason` — patch decision `content` without `reason` → 422 `reason_required`; with `reason` → 200.
  - `test_patch_rejects_unknown_fields` — `patch={"evidence": []}` → 422.
  - `test_approve_clean_counts_only_clean_pending` — returns the number of flag-free pending items; flagged items stay `pending`; second call returns 0.
  - `test_review_blocked_when_not_in_review` — set meeting status `analyzing` → PATCH 409 `not_in_review`, approve-clean 409.
  - `test_topics_endpoint` — returns the payment DB topic whose option `Postgres` is in state `decided` and `MongoDB` is `superseded`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS; suite/ruff/mypy clean.
- [ ] **Step 5:** Commit `feat(api): review items with audit events and bulk-approve clean items`.

---

### Task 8: Publish, export, report & reopen

**Files:**
- Create: `backend/app/services/publish.py`, `backend/app/services/export.py`
- Modify: `backend/app/api/v1/endpoints/meetings.py`, `backend/app/api/v1/endpoints/items.py`
- Test: `tests/backend/unit/test_export.py`, `tests/backend/api/test_publish_api.py`

**Interfaces:**
- Produces:
  - `services/export.py` (pure, no DB): `def render_markdown(ctx: MeetingContext, items: list[MeetingItem], published_at: datetime | None) -> str` and `def render_json(ctx: MeetingContext, items: list[MeetingItem]) -> dict[str, Any]` (`{"meeting": ctx dump, "items": [item dumps]}`). Both include only `approved`/`edited` items and drop `status == superseded` items from the main lists. Markdown layout: `# <title>`, a line `Ngày: dd/mm/yyyy · Dự án: <project or —>`, then one `## <section>` per non-empty type in this order and with these Vietnamese headings: decision `Quyết định`, action_item `Việc cần làm`, blocker `Vướng mắc`, request `Yêu cầu`, open_question `Câu hỏi mở`, knowledge `Tri thức`, feedback `Góp ý`; each item one bullet `- <content>` + ` — <owner>` if owner + ` (hạn dd/mm/yyyy)` if due_date + ` [hh:mm:ss <speaker>]` from the first evidence; decisions with `supersedes` add ` (thay cho: A, B)`.
  - `services/publish.py`: `publish(session, *, principal, meeting_id) -> MeetingSummary` — meeting `in_review` else `Conflict("not_in_review")`; an active job → `Conflict("job_running")`; any `pending` item → `Conflict("pending_items", "Còn N mục chưa duyệt")`; sets `published`, `published_at=now`. `export(session, *, principal, meeting_id, fmt: Literal["md", "json"]) -> tuple[str | bytes, str, str]` (body, media type, filename) — only for `published` meetings else `Conflict("not_published")`. `report_item(session, *, principal, item_id, reason: str) -> None` — meeting must be `published` else 409; event `reported`. `reopen_item(session, *, principal, item_id, reason: str | None) -> MeetingItem` — meeting must be `published`; item → `pending`, event `reopened`, meeting → `in_review` (published_at kept so the UI can show "đã phát hành, đang sửa").
  - Endpoints: `POST /meetings/{id}/publish` → `MeetingSummary`; `GET /meetings/{id}/export?format=md|json` → `Content-Disposition: attachment; filename="<slug-of-title>-<yyyy-mm-dd>.<ext>"` (ASCII slug; md is `text/markdown; charset=utf-8`); `POST /items/{id}/report` (`{reason: str}` 1–1000 chars) → 204; `POST /items/{id}/reopen` (`{reason?: str}`) → `ItemOut`.

- [ ] **Step 1: Write the failing tests**
  - Unit `test_export.py`: build items by hand — one approved decision (`supersedes=["MongoDB"]`), one edited action item with due date, one pending item, one rejected item, one approved but `superseded` decision. Assert markdown contains `## Quyết định`, `(thay cho: MongoDB)`, `(hạn 16/10/2026)`, the `[00:03:30 Lan]` evidence tag, and does not contain the pending/rejected/superseded contents; sections absent when empty; `render_json` items count is 2.
  - API `test_publish_api.py` (marked `db`, uses `seed_analyzed_meeting`):
    - `test_publish_blocked_by_pending_items` → 409 `pending_items` and the message names the count.
    - `test_publish_blocked_by_running_job` — approve all, create a queued job via repository → 409 `job_running`.
    - `test_publish_then_export` — approve all → publish 200 status `published`; `export?format=md` 200, `content-type` starts with `text/markdown`, attachment filename ends `.md`, body contains `PostgreSQL` or `Postgres`; `format=json` parses and has `items`; `format=pdf` → 422.
    - `test_export_before_publish_409`.
    - `test_report_and_reopen_flow` — after publish: report → 204 and an event `reported`; PATCH on that item → 409; reopen → item `pending`, meeting `in_review`; edit + approve; publish again → 200.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS; suite/ruff/mypy clean.
- [ ] **Step 5:** Commit `feat(api): publish minutes, export md/json, report and reopen items`.

---

### Task 9: Org-isolation suite

**Files:**
- Test: `tests/backend/api/test_org_isolation.py`

**Interfaces:**
- Consumes: every endpoint from Tasks 5–8, `seed_analyzed_meeting`, `auth()`.

- [ ] **Step 1: Write the tests** (marked `db`): seed one meeting for `org_b` (published, so report/reopen/export routes are reachable) and keep its meeting id, one item id, and its job id. With `auth(org="org_a")`, call each of: `GET /meetings/{id}`, `POST /meetings/{id}/reanalyze`, `GET /meetings/{id}/items`, `GET /meetings/{id}/topics`, `POST /meetings/{id}/items/approve-clean`, `POST /meetings/{id}/publish`, `GET /meetings/{id}/export?format=md`, `GET /jobs/{job_id}`, `PATCH /items/{item_id}` (approve), `GET /items/{item_id}/events`, `POST /items/{item_id}/report`, `POST /items/{item_id}/reopen` — parametrized; each → 404 with code `not_found`. Then `GET /meetings` for `org_a` → `[]`, and org_b's item `review_state`, event count and meeting status are unchanged (read via repositories with `org_id="org_b"`).
- [ ] **Step 2:** Run. These tests should pass against the code from Tasks 5–8; any failure is a real isolation bug — fix it in the owning service/repository (not in the test) and add the fix to this task's commit.
- [ ] **Step 3:** Commit `test(api): prove cross-org access returns 404 on every endpoint`.

---

### Task 10: Run it — Dockerfile, compose services, Makefile, docs

**Files:**
- Create: `backend/Dockerfile`, `backend/.dockerignore`, `Makefile`
- Modify: `docker-compose.yml` (add `backend` and `worker` per spec §14; DB/Redis URLs overridden in `environment:` to the `db`/`redis` hosts so a `.env` written for host-side dev still works in compose), `.env.example` (add `CORS_ORIGINS`, `MAX_UPLOAD_BYTES`, `TEST_DATABASE_URL`), `evals/README.md` untouched.
- Create: `docs/backend.md` — how to run (compose, migrations, worker, tests incl. `docker compose up -d db` for DB tests and `REQUIRE_DB=1`), Clerk Dashboard setup (JWKS URL, issuer, session-token custom claim `{"name": "{{user.full_name}}"}`, disable personal accounts), API table.

**Interfaces:**
- Dockerfile: `python:3.11-slim`, install uv, `uv sync --frozen --no-dev`, copy `app`, `alembic`, `alembic.ini`; default `CMD` runs uvicorn; compose `backend.command` = `sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"`, `worker.command` = `arq app.workers.main.WorkerSettings`.
- Makefile targets: `up`, `down`, `db` (`docker compose up -d db redis`), `migrate`, `api` (local uvicorn --reload), `worker` (local arq), `test`, `lint` (ruff + mypy).

- [ ] **Step 1:** Write the files.
- [ ] **Step 2:** Verify: `docker compose config` succeeds; `docker compose build backend` succeeds; `docker compose up -d db redis backend` then `curl -s localhost:8000/api/v1/health` → `{"status":"ok"}` and `curl -s -o /dev/null -w "%{http_code}" localhost:8000/api/v1/meetings` → `401`; `docker compose down`. If Docker is unavailable, record that in the report and verify with local `uv run uvicorn app.main:app` instead.
- [ ] **Step 3:** Full suite with `REQUIRE_DB=1` (DB up) → all pass; ruff, mypy clean.
- [ ] **Step 4:** Commit `chore: containerize backend and worker, add Makefile and backend docs`.
