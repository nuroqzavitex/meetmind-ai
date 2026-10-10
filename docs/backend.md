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

1. Tạo application trên Clerk Dashboard, bật **Organizations**; tắt **Personal accounts**
   (người dùng bắt buộc thuộc một organization).
2. Lấy **Frontend API URL**, đặt:
   - `CLERK_JWKS_URL=https://<frontend-api>/.well-known/jwks.json`
   - `CLERK_ISSUER=https://<frontend-api>`
   - `CLERK_AUTHORIZED_PARTIES=http://localhost:3000` (origin của frontend, phân tách bằng dấu phẩy)
3. Sessions → **Customize session token**, thêm claim: `{"name": "{{user.full_name}}"}`
   (backend lưu tên người thao tác vào `item_events`).

Token thiếu/sai → 401; không có organization đang active → 403.

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

Lỗi luôn có dạng `{"error": {"code": "...", "message": "..."}}`: 401, 403, 404 (kể cả truy cập
chéo org), 409, 413 (file quá lớn, `MAX_UPLOAD_BYTES`), 422.
