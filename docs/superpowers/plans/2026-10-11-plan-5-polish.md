# Plan 5 — Hoàn thiện (E2E, CI, README) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đóng mốc M5 của spec: Playwright e2e chạy toàn luồng với LLM giả, GitHub Actions (lint, type, test; eval khi đổi prompt/agent), README đủ để người khác tự dựng và chạy.

**Architecture:** Backend có thêm `LLM_PROVIDER=fake`. Ở chế độ này API và worker dùng `FixtureLLM`, đọc phản hồi JSON theo tên agent từ một thư mục fixture, nên e2e chạy được mà không cần khoá Anthropic. E2E dùng `@playwright/test` cùng `@clerk/testing` (testing token, đăng nhập bằng user test thật trên Clerk dev instance). Cấu hình đặt ở `frontend/`, test nằm ở `tests/e2e/`. CI gồm ba job (backend, frontend, e2e) và một workflow eval riêng; các job cần secret sẽ tự bỏ qua khi secret chưa được cấu hình.

**Tech Stack:** Playwright (`@playwright/test`), `@clerk/testing`, GitHub Actions (`astral-sh/setup-uv`, `actions/setup-node`), service container `pgvector/pgvector:pg16`, pre-commit.

**Spec:** `docs/superpowers/specs/2026-10-10-meetmind-mvp-design.md` (mục 0, 13, 14, 15/M5)

## Global Constraints

- Commit và PR chỉ mang danh tính của người dùng: **không** có dòng `Co-Authored-By`, **không** có dòng "Generated with Claude Code".
- **KHÔNG BAO GIỜ chạy `ruff format`.** Chỉ `ruff check` trên các file mình sửa.
- `tests/` không bao giờ gọi API LLM thật (spec 13.1). E2E chạy backend với LLM giả.
- E2E theo luồng spec 13.1: đăng nhập test (Clerk testing token) → upload → duyệt → phát hành → tải `.md` → hỏi đáp.
- CI chạy eval khi PR đụng tới `backend/app/ai/prompts/` hoặc `backend/app/ai/agents/`, và fail nếu dưới ngưỡng (spec 13.2).
- README, docs và chuỗi giao diện viết bằng tiếng Việt. Code, tên biến và commit message viết bằng tiếng Anh.
- Không bịa số liệu eval. Bảng kết quả chỉ ghi số đã thực sự đo; chưa đo thì ghi "chưa chạy" cùng lệnh để chạy.
- Pytest chạy từ `backend/`: `REQUIRE_DB=1 uv run pytest -q`. Muốn chạy riêng một phần thì dùng `-k`.
- Frontend kiểm tra bằng `npm run lint && npm run typecheck && npm test` trong `frontend/`.

## Review Focus

1. Chế độ `LLM_PROVIDER=fake` không được bật âm thầm trong docker-compose hay `.env.example` mặc định. Mặc định vẫn là `anthropic`, và `fake` cần được đặt tường minh.
2. Thư mục fixture không tồn tại, hoặc thiếu file cho một agent. Khi đó lời gọi phải lỗi rõ ràng (`LLMError` nêu tên agent và đường dẫn), không được crash bằng `FileNotFoundError` thô.
3. E2E chạy lại nhiều lần trên cùng DB, cùng user. Mỗi lần chạy phải dùng project/tiêu đề duy nhất và không phụ thuộc dữ liệu của lần chạy trước (ví dụ `getByText` không được trùng với cuộc họp cũ).
4. CI trên fork hoặc repo chưa có secret. Job e2e và eval phải kết thúc **thành công kèm thông báo bỏ qua**, không được đỏ.
5. Kiểu OpenAPI bị lệch. Nếu backend đổi schema mà quên `npm run gen:types`, CI phải fail.

---

### Task 1: `LLM_PROVIDER=fake` với `FixtureLLM`

**Files:**
- Create: `backend/app/ai/llm/fixture.py`
- Create: `backend/app/core/llm.py`
- Modify: `backend/app/core/config.py` (thêm `llm_provider`, `fake_llm_dir`)
- Modify: `backend/app/api/deps.py` (`get_llm` dùng `build_llm`; chuyển `_UnconfiguredLLM` sang `app/core/llm.py`)
- Modify: `backend/app/workers/main.py` (`startup` dùng `build_llm`)
- Create: `tests/fixtures/llm/payment_v2/qa_filter.json`, `tests/fixtures/llm/payment_v2/qa.json`
- Modify: `.env.example` (dòng `LLM_PROVIDER=anthropic` kèm chú thích `fake` chỉ dùng cho e2e; thêm `FAKE_LLM_DIR=`)
- Test: `tests/backend/unit/test_fixture_llm.py`

**Interfaces:**
- Produces:
  - `FixtureLLM(directory: Path)` là một `LLMClient`. Hàm `structured(*, agent, system, user, schema)` đọc `<directory>/<agent>.json` và trả `schema.model_validate(data)`. Lần gọi nào cũng trả cùng một phản hồi, không pop như `FakeLLM`. Nếu file không tồn tại thì raise `LLMError(f"FixtureLLM: không có fixture cho agent '{agent}' ({path})")`.
  - `build_llm(settings: Settings) -> LLMClient`, theo thứ tự:
    - `settings.llm_provider == "fake"` → `FixtureLLM(Path(settings.fake_llm_dir))`;
    - không có `anthropic_api_key` → `UnconfiguredLLM()`;
    - còn lại → `make_llm(settings.ai_settings(), key)`.
  - `Settings.llm_provider: Literal["anthropic", "fake"] = "anthropic"`, `Settings.fake_llm_dir: str = "../tests/fixtures/llm/payment_v2"` (đường dẫn tương đối tính từ `backend/`).
- Task 2 dùng: backend và worker chạy với `LLM_PROVIDER=fake EMBEDDING_PROVIDER=hash`. Fixture `qa.json` trả `{"answer": "Nhóm đã chốt dùng Postgres cho dịch vụ thanh toán [1].", "used_refs": [1]}`. Fixture `qa_filter.json` trả `{"rewritten_query": "cơ sở dữ liệu dịch vụ thanh toán", "people": [], "item_types": []}`.

- [ ] **Step 1: Viết test hỏng** trong `tests/backend/unit/test_fixture_llm.py`:
  - `test_fixture_llm_returns_same_response_every_call`: dùng `tmp_path` có `qa.json`; gọi hai lần với `schema=QAAnswer`; cả hai đều bằng nhau và `used_refs == [1]`.
  - `test_fixture_llm_missing_agent_raises_llm_error`: `pytest.raises(LLMError, match="agent 'topics'")`.
  - `test_build_llm_fake_provider`: `Settings(llm_provider="fake", fake_llm_dir=str(tmp_path))` → `isinstance(build_llm(s), FixtureLLM)`.
  - `test_build_llm_without_key_is_unconfigured`: `Settings(anthropic_api_key=None)` → gọi `structured(...)` thì raise `LLMError`. Chú ý `_env_file=None` để không đọc `.env` thật.
  - `test_payment_v2_fixture_dir_has_all_pipeline_agents`: `tests/fixtures/llm/payment_v2/` chứa `extract.json`, `topics.json`, `qa_filter.json`, `qa.json`, và `qa.json` validate được bằng `QAAnswer`.
- [ ] **Step 2:** `cd backend && uv run pytest -q -k fixture_llm` → FAIL (import error).
- [ ] **Step 3:** Viết `FixtureLLM`, `build_llm`, các field Settings và hai file fixture QA. Sửa `deps.get_llm` và `workers.main.startup` để dùng `build_llm`.
- [ ] **Step 4:** Thêm `test_pipeline_with_fixture_llm_payment_v2` vào cùng file: `analyze_transcript(ctx=CTX_PAYMENT, filename="payment_v2.txt", data=PAYMENT, llm=FixtureLLM(<payment_v2 dir>), settings=AISettings())` cho ra đúng một `decision` chứa "Postgres". Test này chứng minh fixture không bị gọi lặp trùng (không sinh act trùng).
  - Nếu pipeline gọi `extract` nhiều lần trên payment_v2 (nhiều chunk) thì không được sửa pipeline. Thay vào đó, ghi lại phát hiện này trong report và cho `FixtureLLM` hỗ trợ `<agent>.json` là list, trả phần tử theo vòng lặp.
- [ ] **Step 5:** `cd backend && REQUIRE_DB=1 uv run pytest -q && uv run ruff check app ../tests && uv run mypy` → toàn bộ xanh.
- [ ] **Step 6:** Commit `feat(backend): fake LLM provider backed by fixture files for e2e`.

### Task 2: Playwright e2e với Clerk testing token

**Files:**
- Modify: `frontend/package.json` (devDeps `@playwright/test`, `@clerk/testing`; script `"e2e": "playwright test"`)
- Create: `frontend/playwright.config.ts`
- Create: `tests/e2e/global.setup.ts`, `tests/e2e/full-flow.spec.ts`, `tests/e2e/README.md`
- Modify: `frontend/tsconfig.json` hoặc tạo `tests/e2e/tsconfig.json` để file e2e được typecheck
- Modify: `frontend/.env.example` (thêm `E2E_CLERK_USER_USERNAME`, `E2E_CLERK_USER_PASSWORD`)
- Modify: `Makefile` (target `e2e`); `.gitignore` (`frontend/test-results/`, `frontend/playwright-report/`, `frontend/playwright/.clerk/`)

**Interfaces:**
- Consumes: backend chạy với `LLM_PROVIDER=fake`, `EMBEDDING_PROVIDER=hash` (Task 1).
- Produces (Task 3 gọi): lệnh `cd frontend && npx playwright test`. Các biến môi trường cần có:
  - Clerk: `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `CLERK_JWKS_URL`, `CLERK_ISSUER`.
  - User test: `E2E_CLERK_USER_USERNAME`, `E2E_CLERK_USER_PASSWORD`.
  - Hạ tầng: `DATABASE_URL`, `REDIS_URL` trỏ tới Postgres/Redis đang chạy, đã migrate.

Quyết định:
- `testDir: "../tests/e2e"`, một worker, `retries: process.env.CI ? 1 : 0`, `trace: "retain-on-failure"`, timeout mỗi test 180 s.
- `webServer` gồm ba tiến trình, chạy với `reuseExistingServer: !process.env.CI`:
  1. Backend: `cd ../backend && uv run uvicorn app.main:app --port 8000`, chờ url `http://localhost:8000/health`.
  2. Worker: `cd ../backend && uv run arq app.workers.main.WorkerSettings`. Dùng tuỳ chọn `wait: { stdout: /Starting worker/ }` nếu bản Playwright cài được hỗ trợ; nếu không thì `globalSetup` spawn worker và `globalTeardown` kill nó.
  3. Frontend: CI dùng `npm run build && npm run start`, local dùng `npm run dev`, chờ url `http://localhost:3000`.
  - Env của backend và worker luôn có `LLM_PROVIDER=fake`, `EMBEDDING_PROVIDER=hash`. Các biến khác kế thừa từ `process.env` và `../.env`.
- `global.setup.ts` gọi `clerkSetup()`. Bỏ qua toàn bộ suite bằng `test.skip(...)` kèm thông báo rõ khi thiếu `CLERK_SECRET_KEY` hoặc `E2E_CLERK_USER_USERNAME`.
- User test phải là thành viên của ít nhất một organization. Sau khi đăng nhập, nếu bị chuyển tới `/select-org` thì chọn org đầu tiên.
- Mỗi lần chạy dùng hậu tố `run = Date.now()`: tiêu đề `E2E payment ${run}`, project `e2e-${run}`.

- [ ] **Step 1:** `npm i -D @playwright/test @clerk/testing` (chọn bản `@clerk/testing` tương thích `@clerk/nextjs` 6), rồi `npx playwright install chromium`.
- [ ] **Step 2:** Viết `full-flow.spec.ts`, một test `upload → review → publish → download md → ask with citation`:
  1. `setupClerkTestingToken({ page })`; `clerk.signIn({ page, signInParams: { strategy: "password", identifier, password } })`; xử lý `/select-org`.
  2. Vào `/meetings/new`, điền tiêu đề, project, ngày, người tham dự Lan (người chốt), Minh, Hoa. Upload `tests/fixtures/transcripts/payment_v2.txt`, gửi đi.
  3. Chờ màn duyệt (`/meetings/<id>/review`) hiện mục quyết định chứa "Postgres" (timeout 60 s).
  4. Duyệt mọi mục bằng chính các nút trên giao diện (đọc `src/features/review/*` để biết nhãn), rồi Phát hành.
  5. Ở `/meetings/<id>/minutes`: `page.waitForEvent("download")` khi bấm tải `.md`; `suggestedFilename()` kết thúc bằng `.md`; nội dung file chứa "Postgres".
  6. Vào `/qa`, hỏi "Dịch vụ thanh toán dùng cơ sở dữ liệu gì?". Bọc trong `expect(async () => …).toPass({ timeout: 60_000 })`, gửi lại câu hỏi cho tới khi có ít nhất một citation chip chứa tiêu đề cuộc họp của lần chạy này (chờ job index xong).
  7. Bấm citation chip, URL khớp `/meetings/<id>/minutes?u=`.
  - Dùng selector theo role/label/text tiếng Việt lấy từ code frontend; chỉ thêm `data-testid` khi không có role/label ổn định.
- [ ] **Step 3:** Kiểm tra với điều kiện có thể chạy ở máy dev (chưa có khoá Clerk):
  - `npx playwright test --list` liệt kê đúng 1 test.
  - `npm run typecheck` và `npm run lint` (gồm cả file e2e) xanh.
  - Khi không có env Clerk, `npx playwright test` kết thúc với test ở trạng thái skipped, exit 0. Webserver không được khởi động khi suite bị skip; nếu không tránh được thì ghi vào report.
  - `npm test` (vitest) không được nhặt file `tests/e2e`.
- [ ] **Step 4:** Thêm target `e2e: cd frontend && npx playwright test` vào `Makefile`. Viết `tests/e2e/README.md`, hướng dẫn tạo user test trên Clerk (password, thuộc một org), các env cần có, cách chạy.
- [ ] **Step 5:** Commit `test(e2e): playwright full flow with clerk testing token and fake LLM`.

### Task 3: GitHub Actions, pre-commit, `make eval`

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/workflows/eval.yml`, `.pre-commit-config.yaml`
- Modify: `Makefile` (target `eval`: `run_pipeline` rồi `run_qa`; thêm `e2e eval` vào `.PHONY`)

**Interfaces:**
- Consumes: lệnh e2e của Task 2; `evals.runners.run_pipeline` và `run_qa` (exit 1 nếu dưới ngưỡng).

Quyết định cho `ci.yml` (`on: push` nhánh `main`, `pull_request`; `concurrency` huỷ run cũ cùng ref):
- **backend:**
  - Service `pgvector/pgvector:pg16` (user/pass `app`, DB `meeting`, healthcheck `pg_isready`); `psql` tạo DB `meeting_test`.
  - `astral-sh/setup-uv` có cache; `uv sync` trong `backend/` (không cài extra `embeddings`).
  - `uv run ruff check app ../tests ../evals`; `uv run mypy`.
  - `REQUIRE_DB=1 TEST_DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/meeting_test uv run pytest -q`.
- **frontend:**
  - Node 20 với cache npm, `npm ci`, lint, typecheck, test.
  - `npm run build` với Clerk key giả (giống cách đã build ở plan 3).
  - Kiểm tra lệch kiểu: cài uv, `uv sync` trong backend, `npm run gen:types`, rồi `git diff --exit-code frontend/openapi.json frontend/src/types/api.ts`.
- **e2e:**
  - `needs: [backend, frontend]`. Bước đầu kiểm tra secret `CLERK_SECRET_KEY` và `E2E_CLERK_USER_USERNAME`; thiếu thì `echo "::notice::E2E bỏ qua: chưa cấu hình secret Clerk"` và các bước sau có `if` bỏ qua.
  - Có secret thì: service Postgres và Redis, `uv sync`, `alembic upgrade head`, `npm ci`, `npx playwright install --with-deps chromium`, `npx playwright test`.
  - Upload `playwright-report` khi fail.

Quyết định cho `eval.yml`:
- `on: pull_request` với `paths` gồm `backend/app/ai/prompts/**`, `backend/app/ai/agents/**`, `evals/**`; thêm `workflow_dispatch`.
- Bỏ qua kèm notice khi thiếu secret `ANTHROPIC_API_KEY`.
- Service Postgres (cho `run_qa`, DB `meeting_test`); `uv sync --extra embeddings`; cache `~/.cache/huggingface` bằng `actions/cache`.
- Chạy `PYTHONPATH=.. uv run python -m evals.runners.run_pipeline` và `... run_qa`. Upload `evals/reports/` làm artifact.

`.pre-commit-config.yaml`: các hook `local` chạy `uv run ruff check` (trong backend) và `npm run lint` (trong frontend), không format.

- [ ] **Step 1:** Viết hai workflow và file pre-commit.
- [ ] **Step 2:** Kiểm tra cú pháp YAML: `uv run python -c "import yaml,sys; [yaml.safe_load(open(p)) for p in sys.argv[1:]]" ../.github/workflows/ci.yml ../.github/workflows/eval.yml ../.pre-commit-config.yaml`. Nếu `npx --yes actionlint` hoặc binary actionlint có sẵn thì chạy thêm; không có thì ghi vào report.
- [ ] **Step 3:** Chạy tay đúng các lệnh của job backend và frontend trên máy local (gồm cả kiểm tra lệch kiểu `gen:types` + `git diff --exit-code`) → xanh.
- [ ] **Step 4:** Thêm target `eval` vào Makefile. Commit `ci: github actions for lint/type/test, e2e and prompt-triggered evals`.

### Task 4: README gốc

**Files:**
- Create: `README.md` (gốc repo)
- Modify: `docs/backend.md`, `docs/frontend.md` (chỉ sửa link hoặc trỏ về README khi trùng lặp; thêm mục `LLM_PROVIDER=fake`)

README bằng tiếng Việt, cho người chấm bài, gồm các mục:
1. **Giới thiệu.** Một đoạn về bài toán; badge CI (`https://github.com/nuroqzavitex/meetmind-ai/actions/workflows/ci.yml/badge.svg`).
2. **Tính năng.** Bám danh sách "MVP xong khi" của spec mục 0.
3. **Kiến trúc.** Sơ đồ mermaid: Browser → Next.js (Clerk) → FastAPI → Postgres (pgvector, pg_trgm) / Redis → Arq worker (`analyze`, `index`) → Claude. Kèm pipeline AI: parse → extract → check_quotes → topics → state machine → arbitrate → build_items → validate; và luồng QA: filter → hybrid search + RRF → supersession → answer → check_citations.
4. **Quyết định thiết kế.** Ngắn, mỗi mục 1–2 câu, lấy từ spec và từ các ruling đã ghi:
   - máy trạng thái tất định thay cho để LLM tự chốt;
   - bằng chứng nguyên văn;
   - cách ly org ở repository (404);
   - job bất đồng bộ;
   - RRF lai vector + trigram;
   - supersession khi hỏi đáp;
   - câu từ chối cố định;
   - FakeLLM/FixtureLLM.
5. **Chạy nhanh.**
   - Yêu cầu: Docker, uv, Node 20.
   - Các bước: `cp .env.example .env` → điền khoá → `make up` → mở `http://localhost:3000`.
   - Phương án chạy không Docker: `make db migrate api worker fe-dev`.
6. **Cấu hình Clerk**, từng bước:
   - tạo application;
   - bật Organizations, tắt personal accounts;
   - session token thêm claim `"name": "{{user.full_name}}"` (kiểm tra cú pháp với `backend/app/core/auth.py`);
   - lấy publishable/secret key, JWKS URL, issuer;
   - `CLERK_AUTHORIZED_PARTIES`;
   - tạo user test có password cho e2e.
7. **Biến môi trường.** Bảng tóm tắt, trỏ tới `.env.example`.
8. **Test.** `make test`, `make lint`, `make e2e`, `make types`; nói rõ test không gọi LLM thật.
9. **Đánh giá (evals).**
   - Bảng chỉ số và ngưỡng copy đúng từ `evals/config.yaml`.
   - Cột "Kết quả" ghi "chưa chạy" cùng hướng dẫn `make eval`. Không bịa số.
   - Nhắc golden cần người xác nhận.
10. **Cấu trúc thư mục.** Cây rút gọn.
11. **Giới hạn và hướng phát triển.** STT ngoài phạm vi, bge-m3 tải ~2 GB, chưa có streaming, v.v.

- [ ] **Step 1:** Viết README. Mọi lệnh trong README phải có thật trong Makefile, package.json hoặc docs. Mọi tên biến môi trường phải có trong `.env.example`.
- [ ] **Step 2:** Kiểm tra chéo bằng `grep`: các target `make` mà README nhắc tới đều có trong Makefile; các biến `UPPER_CASE` trong README đều có trong `.env.example` hoặc `frontend/.env.example`.
- [ ] **Step 3:** Commit `docs: root README with architecture, design decisions, setup and evals`.
