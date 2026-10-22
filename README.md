# MeetMind AI

[![CI](https://github.com/nuroqzavitex/meetmind-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/nuroqzavitex/meetmind-ai/actions/workflows/ci.yml)

MeetMind AI biến transcript cuộc họp tiếng Việt thành biên bản có cấu trúc với đúng **trạng thái cuối**:
đề xuất A, cuối buổi chốt B thì B là quyết định, A bị thay thế. Mỗi mục có bằng chứng là câu nói gốc kèm
mốc thời gian. Một thành viên trong nhóm duyệt rồi phát hành. Các cuộc họp đã phát hành tạo thành kho tri
thức của nhóm để hỏi đáp có trích dẫn. Dữ liệu tách theo nhóm (Clerk Organizations).

Đặc tả thiết kế: [docs/superpowers/specs/2026-10-10-meetmind-mvp-design.md](docs/superpowers/specs/2026-10-10-meetmind-mvp-design.md)
(v3, thay [MVP_Spec.md](MVP_Spec.md)). Các tính năng thêm sau có spec riêng trong
[docs/superpowers/specs/](docs/superpowers/specs/). Tài liệu chi tiết: [docs/backend.md](docs/backend.md),
[docs/frontend.md](docs/frontend.md), [docs/deploy.md](docs/deploy.md), [docs/test-cases.md](docs/test-cases.md),
[evals/README.md](evals/README.md), [tests/e2e/README.md](tests/e2e/README.md).

Bản chạy thật: frontend trên Vercel, backend trên Render (xem [Deploy](#deploy)).

## Tính năng

Theo danh sách "MVP xong khi" ở mục 0 của spec, cộng các phần làm thêm (ghi âm, Discord, xin vào tổ chức):

- **Đăng nhập và org.** Đăng nhập bằng Clerk, người dùng phải thuộc một organization. Dữ liệu của org này không lộ sang org khác (có bộ test cách ly). Người mới có thể tạo org hoặc **xin vào org có sẵn bằng mã tham gia**: admin thấy yêu cầu ở chuông trên thanh điều hướng (và trên Discord nếu đã gắn), đồng ý thì backend thêm thành viên qua Clerk Backend API.
- **Upload và duyệt.** Upload transcript (`.txt`, `.srt`, `.vtt`, `.docx`), màn hình duyệt hiển thị 7 loại mục: `decision`, `action_item`, `open_question`, `blocker`, `request`, `feedback`, `knowledge`. Mỗi mục có trích dẫn và mốc thời gian, bấm vào là cuộn tới câu gốc. Tab **Diễn biến chủ đề** cho thấy phương án nào bị thay thế lúc nào.
- **Upload ghi âm.** File `.mp3`, `.m4a`, `.wav`, `.webm`, `.mp4` (≤ 25 MB) được chuyển thành văn bản và tách người nói bằng OpenAI `gpt-4o-transcribe-diarize`. Người dùng gán tên thật và người quyết định cho từng "Người nói A/B…", sau đó luồng phân tích chạy như với transcript.
- **Hàng chờ xác nhận (Mission 3).** Lớp kiểm tra bằng code (`ai/domain/commitment_guard.py`) không để một gợi ý, việc có điều kiện, việc bị người nhận từ chối, câu "chờ tin" hay quyết định bị hiểu ngược ý ("chốt **không** …") thành quyết định hoặc việc chính thức. Những mục này lên đầu màn hình duyệt với lý do và cụm từ gây nghi ngờ được tô sáng; người duyệt xác nhận, chuyển thành câu hỏi mở hoặc bỏ. Biên bản tách phần **Đã chốt** và **Chưa chốt – cần theo dõi**.
- **Tổng hợp.** Trang `/overview` xuyên mọi cuộc họp đã phát hành, không dùng AI: **Chương trình họp kế tiếp** (việc chưa chốt, điều kiện cần theo dõi, việc quá hạn/sắp đến hạn; sao chép hoặc gửi lên Discord), **Việc của tôi** (theo người phụ trách) và **Sổ quyết định** (có phương án bị thay thế). Lọc theo dự án.
- **Kịch bản bẫy.** Các trường hợp A→B, chốt A rồi đổi B, quay lại A, mở lại, bác phương án đã chốt, chốt không rõ phương án và chờ cấp trên đều phải ra đúng trạng thái cuối.
- **Phát hành.** Duyệt xong thì phát hành, tải biên bản `.md` và `.json`. Sau phát hành có thể "Báo sai", mở lại mục, sửa rồi phát hành lại.
- **Discord.** Mỗi org gắn một webhook Discord ở trang **Cài đặt**. Khi phát hành, kênh nhận tóm tắt (quyết định, việc cần làm, link biên bản); mỗi sáng 8h có bản tin việc quá hạn, đến hạn và sắp đến hạn (GitHub Actions gọi `POST /api/v1/internal/digest`). Bot Discord: gõ `/hoi <câu hỏi>` trong server đã liên kết (`/ketnoi <mã>`) để hỏi đáp như trang Hỏi đáp, có trích dẫn; `/chuongtrinh`, `/viec ten:<tên>` và `/quyetdinh` trả về chương trình họp kế tiếp, việc của một người và các quyết định gần đây.
- **Hỏi đáp.** Hỏi trên các cuộc họp đã phát hành của org, câu trả lời có trích dẫn `[cuộc họp · hh:mm:ss · người nói]`. Câu hỏi ngoài dữ liệu nhận câu từ chối cố định.
- **Đánh giá.** `evals/` gồm 15 transcript (10 kịch bản bẫy, 5 transcript thực tế) và 18 câu hỏi QA, có ngưỡng ở mục 13.2 của spec. Đã chạy thật ngày 14/10/2026, kết quả ở [Đánh giá](#đánh-giá-evals).
- **Bộ kiểm thử Mission 2.** [docs/test-cases.md](docs/test-cases.md): 7 tình huống chạy thật (làm tốt, dữ liệu mơ hồ, thất bại) theo format Kỳ vọng → Thực tế → Đạt/Chưa đạt → Điều học được.
- **Phân quyền admin.** Admin của org (vai trò trong Clerk) quản lý mã tham gia, duyệt người xin vào, sửa cài đặt Discord và bot, và xoá vĩnh viễn cuộc họp; thành viên thường chỉ xem.
- **CI.** Lint, type check, test, e2e, và eval khi prompt hoặc agent thay đổi. Commit chỉ sửa tài liệu hoặc script tiện ích không chạy CI.

## Kiến trúc

```mermaid
flowchart LR
    B[Trình duyệt] --> FE["Next.js 15<br/>(Clerk)"]
    FE -- "REST + Bearer JWT<br/>poll trạng thái job" --> API["FastAPI<br/>get_principal → services → repositories(org_id)"]
    API --> PG[("PostgreSQL 16<br/>pgvector + pg_trgm")]
    API -- "enqueue job" --> R[(Redis)]
    R --> W["Arq worker<br/>transcribe, analyze, index, notify"]
    W --> PG
    W --> C["LLM<br/>(Ollama Cloud, OpenAI hoặc Claude)"]
    W --> STT["OpenAI<br/>chuyển giọng nói"]
    API -- "POST /qa" --> C
    W -- "webhook" --> DC["Discord"]
    DC -- "/hoi, /ketnoi, /chuongtrinh, /viec, /quyetdinh<br/>(Interactions Endpoint)" --> API
    GH["GitHub Actions<br/>8h sáng"] -- "POST /internal/digest" --> API
```

Embedding: bge-m3 chạy tại chỗ, hoặc Gemini API (bản deploy dùng Gemini). LLM chọn bằng `LLM_PROVIDER`; bản deploy dùng
Ollama Cloud `gemma4:31b` cho mọi agent (trước 21/10/2026 là OpenAI `gpt-4o-mini`, phân xử `gpt-5-mini`).

Phụ thuộc một chiều: `endpoints → services → repositories / ai`. Thư mục `backend/app/ai/` không biết gì về HTTP,
Clerk hay org, nên cùng một lõi chạy được từ API, worker và runner eval.

**Pipeline phân tích** (job `analyze`, LangGraph, `backend/app/ai/pipeline.py`):

```
normalize (parse) → extract (LLM, song song theo đoạn) → check_quotes ─┐
       ▲                                     đoạn có > 30% act sai trích dẫn │
       └──────────────────── chạy lại extract cho đoạn đó, tối đa 1 lần ────┘
→ topics (LLM) → decide_guard (code) → state_machine (code) → arbitrate (LLM, chỉ khi có dấu hiệu mâu thuẫn)
→ build_items (code) → validate (code)
```

Worker lưu kết quả và cập nhật `jobs.step` / `progress` sau mỗi bước.

**Luồng hỏi đáp** (`POST /api/v1/qa`, `backend/app/services/qa.py`):

```
filter (LLM: dự án, ngày, người, loại mục, câu hỏi viết lại)
→ hybrid search: vector + trigram trên items và transcript_chunks, gộp RRF (k = 60, giữ 12)
→ supersession: đánh dấu ngữ cảnh "mới nhất" / "đã bị thay thế"
→ answer (LLM, chỉ dùng ngữ cảnh đánh số [n])
→ check_citations: bỏ [n] không tồn tại; không còn trích dẫn hợp lệ thì trả câu từ chối
```

## Quyết định thiết kế

- **Máy trạng thái tất định, không để LLM tự chốt.** LLM chỉ gán nhãn hành vi cho từng câu (đề xuất, phản đối, chốt, mở lại...). Code thuần (`ai/domain/state_machine.py`) suy ra trạng thái cuối của từng phương án nên kết quả lặp lại được và kiểm thử được bằng unit test.
- **Không tin câu "chốt" mơ hồ.** `ai/domain/decide_guard.py` chạy trước máy trạng thái: một câu chốt chỉ được tính cho phương án khi chính câu đó nêu tên phương án ("Ok chốt vậy nhé" không được LLM tự điền phương án). Chủ đề đã hoãn ("chờ sếp duyệt") thì câu "ok" chung chung sau đó không tự thành quyết định. Hai luật này được thêm sau khi eval chỉ ra lỗi, xem [docs/test-cases.md](docs/test-cases.md).
- **Bằng chứng nguyên văn.** Mỗi act phải trỏ tới `utterance_id` và trích dẫn khớp đúng câu đó (rapidfuzz `partial_ratio ≥ 90`). Act sai trích dẫn bị loại, mục không còn bằng chứng bị bỏ. Hạn chót tương đối ("thứ Sáu tuần sau") do parser tiếng Việt tính, không do LLM tính.
- **Cách ly org ở repository.** Mọi hàm repository của bảng gốc bắt buộc nhận `org_id`, payload job Arq cũng mang `org_id`. Truy cập tài nguyên của org khác trả **404**, không phải 403, để không lộ việc tài nguyên tồn tại. Bộ test riêng: `tests/backend/api/test_org_isolation.py`.
- **Job bất đồng bộ.** Phân tích và lập chỉ mục chạy trong worker Arq. API trả `job_id` ngay, frontend poll `/jobs/{id}`. Lỗi phân tích hiện ra dạng dễ đọc và có thể chạy lại.
- **Tìm kiếm lai bằng RRF.** Bốn truy vấn (cosine pgvector và `pg_trgm` `word_similarity > 0.2`, mỗi loại trên mục và trên đoạn transcript) được gộp bằng Reciprocal Rank Fusion (k = 60), giữ 12 ngữ cảnh. Vector bắt được câu diễn đạt khác, trigram bắt được tên riêng và thuật ngữ. Mọi truy vấn lọc `org_id` và chỉ lấy cuộc họp `published`.
- **Supersession khi hỏi đáp.** Ngữ cảnh nhắc tới phương án đã bị thay thế được gắn nhãn "đã bị thay thế", quyết định cuối được thêm vào với nhãn "mới nhất". Ngữ cảnh sắp theo ngày họp để LLM trả lời theo trạng thái hiện hành.
- **Câu từ chối cố định.** Không có ngữ cảnh hoặc không còn trích dẫn hợp lệ sau kiểm tra thì trả đúng câu `Không đủ thông tin trong các cuộc họp đã phát hành.` với `citations = []`. Câu cố định giúp test và eval kiểm tra chính xác được.
- **FakeLLM và FixtureLLM.** Test dùng `FakeLLM` (phản hồi theo kịch bản trong bộ nhớ), e2e dùng `FixtureLLM` (`LLM_PROVIDER=fake`, đọc `tests/fixtures/llm/payment_v2/<agent>.json`). Vì vậy test và e2e không gọi LLM thật. Chỉ `evals/` gọi LLM thật.

## Chạy nhanh

**Yêu cầu:** Docker (kèm Docker Compose). Khi chạy không Docker hoặc chạy test: thêm [uv](https://docs.astral.sh/uv/) (tự cài Python 3.11 theo `backend/.python-version`) và Node 22 (≥ 22.22, yêu cầu của jsdom trong Vitest). Cần tài khoản Clerk (xem [Cấu hình Clerk](#cấu-hình-clerk)) và khoá LLM: `ANTHROPIC_API_KEY`, hoặc `OPENAI_API_KEY` với `LLM_PROVIDER=openai`, hoặc `OLLAMA_API_KEY` với `LLM_PROVIDER=ollama`.

```bash
cp .env.example .env     # điền khoá LLM, CLERK_*, NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
make up                  # = docker compose up -d --build
# mở http://localhost:3000
```

`make up` chạy `db` (Postgres + pgvector), `redis`, `backend` (tự chạy `alembic upgrade head` rồi uvicorn, cổng 8000),
`worker` và `frontend` (cổng 3000). Kiểm tra backend: `curl localhost:8000/api/v1/health`. Tắt: `make down`.

Lần đầu phát hành hoặc hỏi đáp với `EMBEDDING_PROVIDER=local`, backend và worker tải model bge-m3 (khoảng 2 GB) vào volume
`hf-cache`. Không muốn tải model: đặt `EMBEDDING_PROVIDER=gemini`, `EMBEDDING_MODEL=gemini-embedding-001`, `GEMINI_API_KEY`
và `INSTALL_EMBEDDINGS=false` (image không cài torch), hoặc `EMBEDDING_PROVIDER=hash` để thử nhanh (chất lượng tìm kiếm thấp hơn).

**Chạy không Docker cho app** (chỉ Postgres và Redis chạy trong Docker):

```bash
cd backend && uv sync --extra embeddings && cd ..   # bỏ --extra embeddings nếu dùng EMBEDDING_PROVIDER=gemini hoặc hash
cd frontend && npm install && cd ..
cp frontend/.env.example frontend/.env.local         # điền khoá Clerk cho frontend
# trong .env: đổi host db / redis thành localhost
make db         # chỉ bật db + redis
make migrate    # alembic upgrade head
make api        # terminal 1: uvicorn --reload, cổng 8000
make worker     # terminal 2: arq worker
make fe-dev     # terminal 3: next dev, cổng 3000
```

**Windows không có `make`:** dùng Git Bash có cài `make`, hoặc chạy lệnh gốc trong [Makefile](Makefile). Các bước chính trong PowerShell (mỗi lệnh chạy từ gốc repo; api, worker và frontend mỗi cái một terminal):

```powershell
Copy-Item .env.example .env
docker compose up -d --build                                   # make up
docker compose up -d db redis                                  # make db
cd backend; uv run alembic upgrade head                        # make migrate
cd backend; uv run uvicorn app.main:app --reload --port 8000   # make api
cd backend; uv run arq app.workers.main.WorkerSettings         # make worker
cd frontend; npm run dev                                       # make fe-dev
```

## Deploy

Frontend lên Vercel, backend và worker lên Render (một web service miễn phí), Postgres trên Neon, Redis trên Upstash.
Cấu hình Render nằm sẵn trong [render.yaml](render.yaml); hướng dẫn từng bước: [docs/deploy.md](docs/deploy.md).

## Cấu hình Clerk

1. Tạo application trên [Clerk Dashboard](https://dashboard.clerk.com) (instance **development**).
2. Bật **Organizations**, đặt **Membership optional** (cho phép tài khoản chưa thuộc org đăng nhập). Không chọn "Membership required": khi đó Clerk tự hiện màn hình tạo org của riêng nó ngay sau đăng nhập, người mới không thấy ô "xin vào tổ chức bằng mã". App vẫn bắt buộc phải có org: chưa có org đang hoạt động thì chuyển tới `/select-org` (tạo org hoặc xin vào org có sẵn), và backend từ chối mọi API dữ liệu.
3. **Sessions → Customize session token**, thêm claim:
   ```json
   { "name": "{{user.full_name}}" }
   ```
   Backend lấy tên người thao tác từ claim `name` (thiếu thì dùng `sub`) để ghi vào lịch sử mục. Org lấy từ claim `o.id` (session token v2) hoặc `org_id` (v1), có sẵn khi người dùng có org đang hoạt động.
4. Trong **API keys**, lấy:
   - Publishable key → `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
   - Secret key → `CLERK_SECRET_KEY`
   - Frontend API URL `https://<frontend-api>` → `CLERK_ISSUER=https://<frontend-api>` và `CLERK_JWKS_URL=https://<frontend-api>/.well-known/jwks.json`
5. `CLERK_AUTHORIZED_PARTIES=http://localhost:3000`: danh sách origin của frontend (phân tách bằng dấu phẩy). Backend từ chối token có `azp` ngoài danh sách này.
6. Cho e2e: bật đăng nhập bằng **Password**, tạo một user có mật khẩu (không bật MFA), thêm vào một organization, rồi điền `E2E_CLERK_USER_USERNAME` và `E2E_CLERK_USER_PASSWORD`. Chi tiết: [tests/e2e/README.md](tests/e2e/README.md).

Token thiếu hoặc sai trả 401, không có org đang hoạt động trả 403.

## Biến môi trường

Danh sách đầy đủ và giá trị mặc định nằm ở [.env.example](.env.example) (dùng cho Docker Compose và backend) và
[frontend/.env.example](frontend/.env.example) (sao chép thành `frontend/.env.local` khi chạy `npm run dev`).

| Biến | Ý nghĩa |
|---|---|
| `ANTHROPIC_API_KEY` | Khoá Anthropic cho pipeline, hỏi đáp và eval |
| `OPENAI_API_KEY` | Khoá OpenAI, dùng khi `LLM_PROVIDER=openai` và cho upload ghi âm |
| `OLLAMA_API_KEY`, `OLLAMA_BASE_URL` | Khoá Ollama Cloud và endpoint (mặc định `https://ollama.com/v1`), dùng khi `LLM_PROVIDER=ollama` |
| `DATABASE_URL`, `REDIS_URL` | Postgres và Redis. Host `db` / `redis` trong Compose, `localhost` khi chạy local |
| `CLERK_JWKS_URL`, `CLERK_ISSUER`, `CLERK_AUTHORIZED_PARTIES` | Backend xác thực JWT của Clerk |
| `CLERK_SECRET_KEY` (backend) | Đọc tên/email người xin vào org và thêm thành viên khi admin đồng ý. Thiếu thì tính năng xin vào org trả 503 |
| `LLM_PROVIDER` | `anthropic` (mặc định), `openai` (cần `OPENAI_API_KEY`, đặt `LLM_MODEL_*` thành model OpenAI), `ollama` (cần `OLLAMA_API_KEY`, ví dụ `gemma4:31b`) hoặc `fake` (chỉ dùng cho e2e, đọc fixture, không gọi LLM thật) |
| `LLM_MODEL_DEFAULT`, `LLM_MODEL_ARBITRATE` | Model cho các agent và cho arbitrate (tên model của nhà cung cấp đang chọn) |
| `PROMPT_VERSION` | Phiên bản prompt (`ai/prompts/<agent>/vN.md`) |
| `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIM` | `local` (bge-m3, 1024 chiều), `gemini` (`gemini-embedding-001`, cần `GEMINI_API_KEY`) hoặc `hash` |
| `INSTALL_EMBEDDINGS` | Build arg của Compose: `false` thì image backend/worker không cài torch |
| `CORS_ORIGINS`, `MAX_UPLOAD_BYTES` | Origin được phép gọi API, kích thước transcript tối đa |
| `MAX_AUDIO_BYTES`, `STT_MODEL` | Kích thước file ghi âm tối đa (mặc định 25 MB) và model chuyển giọng nói (dùng `OPENAI_API_KEY`) |
| `DISCORD_APP_ID`, `DISCORD_PUBLIC_KEY`, `DISCORD_BOT_TOKEN` | Bot hỏi đáp Discord (`/hoi`); token chỉ dùng cho script đăng ký lệnh. Hướng dẫn: [docs/deploy.md](docs/deploy.md#7-bot-hỏi-đáp-discord-tuỳ-chọn) |
| `FRONTEND_URL`, `CRON_SECRET` | URL frontend dùng cho link trong tin Discord; secret bảo vệ endpoint bản tin hằng ngày (rỗng = tắt) |
| `TEST_DATABASE_URL` | DB cho test và eval QA (tên phải kết thúc bằng `_test`) |
| `NEXT_PUBLIC_API_URL` | URL backend mà trình duyệt gọi, mặc định `http://localhost:8000` |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY` | Khoá Clerk cho frontend |
| `E2E_CLERK_USER_USERNAME`, `E2E_CLERK_USER_PASSWORD` | User test cho Playwright |

`NEXT_PUBLIC_*` được nhúng lúc build: đổi giá trị thì phải build lại (`make up`).

## Test

Test không gọi LLM thật: backend dùng `FakeLLM`, JWT ký bằng khoá test và JWKS giả; frontend mock Clerk và API;
e2e dùng `LLM_PROVIDER=fake` và `EMBEDDING_PROVIDER=hash`.

Chuẩn bị: `cd backend && uv sync`, `cd frontend && npm install`; riêng e2e cần thêm db + redis chạy và đã migrate,
truy cập qua `localhost` (`make db && make migrate`). Nếu volume `pgdata` có từ trước khi thêm script init (thiếu DB
`meeting_test`): `docker compose exec db psql -U app -d meeting -c "CREATE DATABASE meeting_test"`.

```bash
docker compose up -d db   # test DB cần Postgres (DB meeting_test do docker/postgres-init tạo)
make test                 # backend pytest (bắt buộc có Postgres) rồi frontend: eslint + tsc + vitest
make lint                 # ruff + mypy cho backend
make types                # sinh lại frontend/src/types/api.ts từ OpenAPI của backend
make e2e                  # Playwright: đăng nhập → upload → duyệt → phát hành → tải .md → hỏi đáp
```

Lần chạy gần nhất (15/10/2026): backend 598 test, frontend 141 test. E2E cần user test Clerk và chạy
`cd frontend && npx playwright install chromium` lần đầu, xem [tests/e2e/README.md](tests/e2e/README.md).
CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) chạy lint, type, test, build, kiểm tra type API
không lệch; e2e tự bỏ qua khi chưa cấu hình secret Clerk. Commit chỉ sửa `scripts/**`, `docs/**`, `*.md` hoặc
`.gitignore` không chạy CI.

## Đánh giá (evals)

`evals/` gọi LLM thật trên 15 transcript (10 kịch bản bẫy, 5 transcript thực tế) và 18 câu hỏi QA, rồi so với golden.
Runner thoát với mã 1 nếu có chỉ số dưới ngưỡng. Ngưỡng lấy từ [evals/config.yaml](evals/config.yaml).

Kết quả chạy ngày 14/10/2026 với `gpt-4o-mini` (phân xử `gpt-5-mini`), trước và sau khi thêm `decide_guard` và mẫu
hạn "trong vòng N ngày" (sau khi sửa chạy 2 lần vì LLM dao động). Phân tích từng tình huống: [docs/test-cases.md](docs/test-cases.md).

| Chỉ số | Ngưỡng | Trước | Sau |
|---|---|---|---|
| `precision` | ≥ 0.85 | 0.61 | 0.69 |
| `recall` | ≥ 0.75 | 0.63 | 0.66 |
| `final_decision_accuracy` | ≥ 0.90 | 0.73 | 0.85 – 0.88 |
| `owner_due_accuracy` | ≥ 0.85 | 0.78 | 0.85 – 0.89 |
| `evidence_faithfulness` | ≥ 1.00 | 1.00 | 1.00 |
| `trap_accuracy` | ≥ 1.00 | 0.70 | 0.80 – 0.90 |
| `qa_citation_accuracy` | ≥ 0.85 | chưa chạy (`make eval-qa`) | |
| `qa_latest_state_accuracy` | ≥ 1.00 | chưa chạy | |
| `qa_refusal_accuracy` | ≥ 1.00 | chưa chạy | |

Bằng chứng luôn đúng nguyên văn; phần chưa đạt nằm ở chất lượng gán nhãn của model nhỏ (sót ý phụ, mục thừa). Bước tiếp
theo là chạy lại với model mạnh hơn cho bước trích xuất (thiết kế gốc dùng Claude Sonnet).

Chạy: eval pipeline dùng provider đang chọn (`LLM_PROVIDER` và khoá tương ứng); eval QA hiện vẫn gọi Claude (`ANTHROPIC_API_KEY`); eval QA cần thêm Postgres (`docker compose up -d db`, `TEST_DATABASE_URL`) và
`uv sync --extra embeddings` trong `backend/` khi dùng embedder `local`. `make eval` chạy cả hai runner, `make eval-qa`
chỉ chạy QA. Báo cáo ghi vào `evals/reports/`.

Transcript và golden được soạn nháp bằng Claude. **Golden cần người xem lại và xác nhận** trước khi dùng làm chuẩn
(spec 13.2). Workflow [eval.yml](.github/workflows/eval.yml) chạy eval khi PR đụng tới `backend/app/ai/prompts/`,
`backend/app/ai/agents/` hoặc `evals/`, và tự bỏ qua khi chưa có secret `ANTHROPIC_API_KEY`.
Chi tiết dataset và quy ước gán nhãn: [evals/README.md](evals/README.md).

## Cấu trúc thư mục

```
backend/
  app/
    ai/            lõi AI: agents/, domain/ (máy trạng thái, decide_guard, hạn chót), llm/, prompts/, retrieval/, stt/, pipeline.py
    api/           endpoint FastAPI (/api/v1)
    core/          cấu hình, xác thực Clerk (+ quyền admin), client Clerk Backend API, lỗi
    models/ db/    SQLAlchemy
    notify/        Discord: webhook, định dạng tin, bot /hoi
    repositories/  truy cập dữ liệu, luôn lọc org_id
    services/      nghiệp vụ: phân tích, chuyển giọng nói, duyệt, phát hành, hỏi đáp, Discord, xin vào tổ chức
    workers/       Arq worker (transcribe, analyze, index, notify)
  alembic/         migration
  scripts/         xuất OpenAPI, đăng ký lệnh Discord
frontend/
  src/app/         route Next.js (App Router)
  src/features/    meetings, review, topics, minutes, qa, speakers, settings, orgs
  tests/           Vitest
tests/
  backend/         unit, integration, db, api (gồm test_org_isolation.py)
  e2e/             Playwright
  fixtures/        transcript và phản hồi LLM cho FixtureLLM
evals/             datasets/, golden/, metrics/, runners/, config.yaml
docker/            script khởi tạo Postgres (DB test)
docs/              tài liệu backend, frontend, deploy, bộ kiểm thử, spec và kế hoạch
scripts/           tiện ích cá nhân (ghi log prompt AI), không ảnh hưởng app
render.yaml        cấu hình Render (backend + worker)
```

## Giới hạn và hướng phát triển

- **Chuyển giọng nói qua API.** Ghi âm dùng OpenAI `gpt-4o-transcribe-diarize` (cần `OPENAI_API_KEY`), giới hạn 25 MB mỗi file, chưa cắt file dài, chưa ghi âm trực tiếp trên trình duyệt; tên người nói phải gán tay.
- **Model embedding nặng.** bge-m3 tải khoảng 2 GB lần đầu và API, worker mỗi bên giữ một bản trong RAM. Image Docker cài torch bản CPU.
- **Hỏi đáp một lượt, không streaming.** Không nhớ hội thoại, câu trả lời trả về một lần.
- **Chuỗi thay thế chỉ trong một cuộc họp.** Nối quyết định xuyên cuộc họp và phát hiện mâu thuẫn với quyết định cũ là P2.
- **Phân quyền còn thô.** Chỉ phân biệt admin và thành viên; mọi thành viên đều duyệt và phát hành được cuộc họp.
- **Eval chưa đạt ngưỡng.** Chạy với model nhỏ, precision/recall còn thấp; eval QA chưa chạy; golden cần người xác nhận.
- **Bot Discord trên gói miễn phí.** Render Free ngủ sau 15 phút, nên cần một cron gọi `/api/v1/health` mỗi 10 phút để bot trả lời kịp 3 giây; mọi người trong server đã liên kết đều đọc được nội dung đã phát hành qua bot.
- **Chưa tích hợp** Jira, Notion, Slack, bot họp thời gian thực (P2).
