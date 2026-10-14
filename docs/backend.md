# Backend (FastAPI + arq + Postgres)

## Chạy bằng Docker Compose

```bash
cp .env.example .env        # điền ANTHROPIC_API_KEY và các biến CLERK_*
docker compose up -d --build   # hoặc: make up
curl localhost:8000/api/v1/health   # {"status":"ok"}
```

Compose chạy `db` (Postgres + pgvector), `redis`, `backend` (tự chạy `alembic upgrade head`
rồi uvicorn) và `worker` (`arq app.workers.main.WorkerSettings`). `DATABASE_URL` / `REDIS_URL`
trong compose được ghi đè về host `db` / `redis`, nên `.env` viết cho chạy local vẫn dùng được.
`docker compose down` giữ nguyên volume dữ liệu (không dùng `-v` nếu muốn giữ DB).

## Chạy local (không container cho app)

```bash
make db        # chỉ bật db + redis
make migrate   # alembic upgrade head
make api       # uvicorn --reload (cổng 8000)
make worker    # arq worker (terminal khác)
```

Trong `.env` dùng `localhost` thay cho `db` / `redis` khi chạy local.

## Test

```bash
docker compose up -d db          # test DB cần Postgres (DB `meeting_test` tạo bởi docker/postgres-init)
cd backend && REQUIRE_DB=1 uv run pytest   # hoặc: make test
make lint                         # ruff + mypy
```

Không có `REQUIRE_DB=1` thì test DB tự skip khi không kết nối được Postgres; có biến này thì fail.
`TEST_DATABASE_URL` mặc định `postgresql+asyncpg://app:app@localhost:5432/meeting_test`.
Test không gọi LLM hay Clerk thật.

## Cấu hình Clerk

Xem [README → Cấu hình Clerk](../README.md#cấu-hình-clerk) (Organizations, claim `name` trong session token,
`CLERK_JWKS_URL`, `CLERK_ISSUER`, `CLERK_AUTHORIZED_PARTIES`, user test cho e2e).
Token thiếu/sai → 401; không có organization đang active → 403.

## LLM giả cho e2e (`LLM_PROVIDER=fake`)

`LLM_PROVIDER=fake` thay Anthropic bằng `FixtureLLM`: mỗi lời gọi của agent `<agent>` trả nội dung file
`<FAKE_LLM_DIR>/<agent>.json` (mặc định `../tests/fixtures/llm/payment_v2`, tính từ `backend/`), không gọi mạng.
Chỉ dùng cho e2e (Playwright tự đặt biến này cho backend và worker, xem [tests/e2e/README.md](../tests/e2e/README.md));
không dùng khi chạy thật hay eval. Unit/integration test dùng `FakeLLM` trong code, không cần biến này.

## API (`/api/v1`, mọi route trừ health cần Bearer token)

| Method | Path | Mô tả |
|---|---|---|
| GET | `/health` | Kiểm tra sống (không cần token) |
| POST | `/meetings` | Upload transcript (multipart: `file`, `context` JSON) → 201, tạo job analyze |
| GET | `/meetings` | Danh sách cuộc họp của org |
| GET | `/meetings/{id}` | Chi tiết cuộc họp |
| POST | `/meetings/{id}/reanalyze` | Phân tích lại → 202 |
| GET | `/meetings/{id}/items` | Các item AI trích xuất |
| GET | `/meetings/{id}/topics` | Các chủ đề |
| POST | `/meetings/{id}/items/approve-clean` | Duyệt hàng loạt các item sạch |
| POST | `/meetings/{id}/publish` | Xuất bản cuộc họp |
| GET | `/meetings/{id}/export` | Xuất biên bản |
| PATCH | `/items/{item_id}` | Duyệt / sửa / từ chối item |
| GET | `/items/{item_id}/events` | Lịch sử thao tác của item |
| POST | `/items/{item_id}/report` | Báo lỗi item (204) |
| POST | `/items/{item_id}/reopen` | Mở lại item |
| GET | `/jobs/{job_id}` | Trạng thái job phân tích |
| POST | `/qa` | Hỏi đáp trên các cuộc họp đã phát hành của org, trả lời kèm trích dẫn |

Lỗi luôn có dạng `{"error": {"code": "...", "message": "..."}}`: 401, 403, 404 (kể cả truy cập
chéo org), 409, 413 (file quá lớn, `MAX_UPLOAD_BYTES`), 422.

## Hỏi đáp (Q&A)

`POST /api/v1/qa` trả lời câu hỏi chỉ dựa trên các cuộc họp **đã phát hành** của org hiện tại
(mọi truy vấn lọc `org_id` và `status = 'published'`). Không đủ căn cứ thì trả đúng câu
`Không đủ thông tin trong các cuộc họp đã phát hành.` với `citations = []`.

- **Job index**: khi publish, backend tạo job `index` (arq) để lập chỉ mục: mỗi item đã
  `approved`/`edited` thành một `search_text`, transcript được cắt thành cửa sổ 6 câu, chồng 2 câu.
  Lỗi index không làm đổi trạng thái cuộc họp. Sửa/từ chối một mục sẽ xoá chỉ mục của mục đó; lần publish lại sẽ lập chỉ mục lại các mục đã đổi.
- **Embedder** (`EMBEDDING_PROVIDER`): `local` (mặc định) dùng sentence-transformers với
  `EMBEDDING_MODEL=BAAI/bge-m3`, `EMBEDDING_DIM=1024`; `hash` là embedder xác định, không tải model,
  chất lượng thấp hơn (dùng cho test và kiểm tra nhanh); `gemini` gọi Gemini API
  (`EMBEDDING_MODEL=gemini-embedding-001`, cần `GEMINI_API_KEY`), xin đúng `EMBEDDING_DIM` chiều rồi chuẩn hoá L2,
  không tải model. Dùng `gemini` hoặc `hash` thì có thể build image không có torch: `INSTALL_EMBEDDINGS=false`.
  Đổi provider sau khi đã index thì vector cũ và mới không so sánh được: phát hành lại để index lại.
- **Bộ nhớ**: API và worker mỗi bên giữ một bản model trong RAM khi dùng `local` (nạp lười, một lần mỗi tiến trình).
- **Lần chạy đầu tiên** với `local` phải tải model bge-m3 (~2 GB). Compose gắn volume `hf-cache`
  (`/root/.cache/huggingface`) cho `backend` và `worker` nên chỉ tải một lần. Image cài torch bản CPU.
- Truy hồi: vector + từ khoá (RRF), giữ 12 ngữ cảnh, sắp theo ngày họp tăng dần; cuộc họp mới nhất là
  trạng thái hiện hành.
- Đánh giá chất lượng: `make eval-qa` (xem `evals/README.md`; `--embedder local` cần `uv sync --extra embeddings`).
