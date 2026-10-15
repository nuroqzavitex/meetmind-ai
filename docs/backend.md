# Backend (FastAPI + arq + Postgres)

## Chạy bằng Docker Compose

```bash
cp .env.example .env        # điền khoá LLM (ANTHROPIC_API_KEY hoặc OPENAI_API_KEY + LLM_PROVIDER=openai) và CLERK_*
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
Token thiếu/sai → 401; không có organization đang active → 403 (trừ các endpoint của người xin vào tổ chức).
Vai trò admin lấy từ claim `o.rol` (`admin`, token v2) hoặc `org_role` (`org:admin`, v1); thao tác chỉ dành cho admin
trả 403 `admin_only`. Duyệt người xin vào tổ chức cần `CLERK_SECRET_KEY` ở backend (gọi Clerk Backend API).

## LLM giả cho e2e (`LLM_PROVIDER=fake`)

`LLM_PROVIDER` chọn `anthropic` (mặc định), `openai` (strict JSON schema, cần `OPENAI_API_KEY`) hoặc `fake`.
`LLM_PROVIDER=fake` thay LLM thật bằng `FixtureLLM`: mỗi lời gọi của agent `<agent>` trả nội dung file
`<FAKE_LLM_DIR>/<agent>.json` (mặc định `../tests/fixtures/llm/payment_v2`, tính từ `backend/`), không gọi mạng.
Chỉ dùng cho e2e (Playwright tự đặt biến này cho backend và worker, xem [tests/e2e/README.md](../tests/e2e/README.md));
không dùng khi chạy thật hay eval. Unit/integration test dùng `FakeLLM` trong code, không cần biến này.

## API (`/api/v1`, mọi route trừ health cần Bearer token)

| Method | Path | Mô tả |
|---|---|---|
| GET | `/health` | Kiểm tra sống (không cần token) |
| POST | `/meetings` | Upload transcript hoặc file ghi âm (multipart: `file`, `context` JSON) → 201, tạo job analyze (transcript) hoặc transcribe (ghi âm) |
| GET | `/meetings/{id}/speakers` | Người nói trong bản ghi âm đã chuyển văn bản (số câu, câu mẫu); chỉ khi `awaiting_speakers` |
| POST | `/meetings/{id}/speakers` | Gán tên thật và người quyết định cho từng "Người nói A/B…" → 202, tạo job analyze |
| GET | `/meetings` | Danh sách cuộc họp của org |
| GET | `/meetings/{id}` | Chi tiết cuộc họp |
| POST | `/meetings/{id}/reanalyze` | Phân tích lại → 202 |
| DELETE | `/meetings/{id}` | Xoá vĩnh viễn cuộc họp và mọi dữ liệu con (admin, 204); 409 `job_running` khi đang chuyển giọng nói/phân tích |
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
| GET / PUT | `/settings/discord` | Webhook (chỉ trả 4 ký tự cuối), bản tin 8h sáng, link mời server. Mọi thành viên đọc, chỉ admin sửa |
| POST | `/settings/discord/test` | Gửi tin thử vào webhook (admin) |
| GET | `/settings/discord-bot` | Trạng thái bot `/hoi`, mã liên kết, link mời bot (admin) |
| POST | `/settings/discord-bot/rotate-code`, `/settings/discord-bot/unlink` | Đổi mã liên kết, huỷ liên kết server (admin) |
| GET | `/settings/join-code` | Mã tham gia tổ chức `MM-XXXX-XXXX` (admin) |
| POST | `/settings/join-code/rotate` | Đổi mã tham gia (admin) |
| POST | `/join-requests` | Xin vào tổ chức bằng mã (không cần org đang active) → 201 |
| GET | `/join-requests/mine` | Yêu cầu của mình và trạng thái (không cần org) |
| DELETE | `/join-requests/{id}` | Huỷ yêu cầu đang chờ của mình (không cần org) |
| GET | `/join-requests` | Yêu cầu đang chờ của tổ chức (admin) |
| POST | `/join-requests/{id}/approve`, `/join-requests/{id}/reject` | Đồng ý (thêm thành viên qua Clerk) / từ chối (admin) |
| POST | `/internal/digest` | Bản tin nhắc việc hằng ngày; header `X-Cron-Secret` = `CRON_SECRET`, không dùng Clerk |
| POST | `/discord/interactions` | Interactions Endpoint của bot Discord; xác thực chữ ký Ed25519, không dùng Clerk |

Lỗi luôn có dạng `{"error": {"code": "...", "message": "..."}}`: 401, 403, 404 (kể cả truy cập
chéo org), 409, 413 (file quá lớn, `MAX_UPLOAD_BYTES` / `MAX_AUDIO_BYTES`), 422, 429 (quá nhiều yêu cầu xin vào
đang chờ), 502 (Discord/Clerk từ chối), 503 (dịch vụ ngoài chưa cấu hình hoặc chưa sẵn sàng).

## Job nền (Arq)

| Job | Khi nào | Việc |
|---|---|---|
| `transcribe` | Upload file ghi âm | OpenAI `gpt-4o-transcribe-diarize` → transcript `.txt` có "Người nói A/B…", trạng thái `awaiting_speakers` |
| `analyze` | Upload transcript, gán xong người nói, phân tích lại | Pipeline LangGraph → các mục chờ duyệt |
| `index` | Phát hành | Lập chỉ mục cho hỏi đáp |
| `notify` | Phát hành, khi org đã gắn webhook | Gửi tóm tắt cuộc họp vào Discord (không tạo hàng `jobs`, lỗi chỉ ghi log) |

`WORKER_POLL_DELAY` (mặc định 0.5 s, bản deploy đặt 10 s để tiết kiệm lệnh Redis của Upstash) là khoảng cách giữa
hai lần worker hỏi hàng đợi.

## Discord

- **Webhook** (`notify/discord.py`, `services/notifications.py`): chỉ nhận URL `https://discord.com/api/webhooks/…`,
  tin nhắn luôn tắt mention (`allowed_mentions: {"parse": []}`) để nội dung transcript không ping cả server.
- **Bản tin 8h sáng**: `.github/workflows/digest.yml` gọi `POST /internal/digest` lúc 01:00 UTC; việc quá hạn (7 ngày
  gần nhất), đến hạn hôm nay và trong 2 ngày tới, theo giờ Việt Nam.
- **Bot `/hoi`** (`api/v1/endpoints/discord.py`, `services/discord_bot.py`): trả lời "đang suy nghĩ" ngay (Discord
  chỉ chờ 3 giây), chạy `services/qa.ask` cho org đã liên kết rồi sửa tin bằng câu trả lời. `/ketnoi <mã>` (cần quyền
  quản lý server) liên kết server với org. Đăng ký lệnh một lần: `uv run python scripts/register_discord_commands.py`
  (cần `DISCORD_APP_ID`, `DISCORD_BOT_TOKEN`). Cách cấu hình: [deploy.md, mục 7](deploy.md#7-bot-hỏi-đáp-discord-tuỳ-chọn).

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
