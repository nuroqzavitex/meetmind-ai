# Deploy: Vercel + Render + Neon + Upstash

Kiến trúc khi deploy:

| Thành phần | Dịch vụ | Gói |
|---|---|---|
| Frontend Next.js | Vercel | Hobby (miễn phí) |
| Backend FastAPI + worker Arq | Render (một web service, hai tiến trình) | Free |
| Postgres + pgvector + pg_trgm | Neon | Free |
| Redis (hàng đợi job) | Upstash | Free |
| Đăng nhập, tổ chức | Clerk (instance Development) | Free |

Gói Free của Render không có background worker, nên `render.yaml` chạy worker và API trong cùng một container.
Render Free "ngủ" sau 15 phút không có request: lần mở đầu tiên sau đó chờ khoảng 30–60 giây.

Nên chọn cùng khu vực Singapore cho Render, Neon và Upstash để giảm độ trễ.

## 1. Neon (Postgres)

1. Đăng ký [neon.tech](https://neon.tech), tạo project, chọn region **AWS Asia Pacific (Singapore)**.
2. Ở **Connection Details**, copy connection string dạng
   `postgresql://<user>:<password>@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require`.
   Dán nguyên chuỗi này vào `DATABASE_URL` ở bước 3: backend tự đổi sang dạng asyncpg.
3. Không cần tạo bảng hay extension bằng tay: lần khởi động đầu, backend chạy `alembic upgrade head`,
   migration bật `vector` và `pg_trgm`.

## 2. Upstash (Redis)

1. Đăng ký [upstash.com](https://upstash.com), **Create Database** (Redis), region **ap-southeast-1 (Singapore)**.
2. Mở tab **TCP** trong khung Connect (không phải REST), hiện mật khẩu rồi copy URL dạng
   `rediss://default:<password>@<host>.upstash.io:6379`. Phải là `rediss` (hai chữ s, TLS);
   nếu chỉ thấy lệnh `redis-cli --tls -u redis://...` thì tự đổi `redis://` thành `rediss://`.
3. Gói Free giới hạn 500k lệnh/tháng. Worker hỏi Redis khoảng 1 lệnh mỗi lần kiểm tra job;
   `render.yaml` đặt `WORKER_POLL_DELAY=10` (khoảng 260k lệnh/tháng kể cả khi service không ngủ).
   Đổi lại 0.5 giây thì hết hạn mức trong vài ngày.

## 3. Render (backend + worker)

1. Đăng ký [render.com](https://render.com) bằng GitHub.
2. **New → Blueprint**, chọn repo `meetmind-ai`. Render đọc `render.yaml` ở gốc repo và tạo service `meetmind-api`.
3. Điền các biến được hỏi:

   | Biến | Giá trị |
   |---|---|
   | `DATABASE_URL` | Connection string của Neon (bước 1) |
   | `REDIS_URL` | URL Upstash (bước 2) |
   | `CLERK_JWKS_URL` | `https://<frontend-api>.clerk.accounts.dev/.well-known/jwks.json` |
   | `CLERK_ISSUER` | `https://<frontend-api>.clerk.accounts.dev` |
   | `CLERK_SECRET_KEY` | Secret key của Clerk (`sk_test_…`), giống biến cùng tên trên Vercel. Cần cho tính năng xin vào tổ chức |
   | `CLERK_AUTHORIZED_PARTIES` | URL Vercel, ví dụ `https://meetmind-ai.vercel.app` (chưa có thì tạm điền, sửa sau bước 4) |
   | `CORS_ORIGINS` | Giống `CLERK_AUTHORIZED_PARTIES` |
   | `OLLAMA_API_KEY` | Khoá Ollama Cloud (https://ollama.com/settings/keys), dùng cho phân tích và hỏi đáp |
   | `OPENAI_API_KEY` | Khoá OpenAI, chỉ dùng cho upload ghi âm (chuyển giọng nói). Bỏ trống thì upload ghi âm báo lỗi |
   | `GEMINI_API_KEY` | Khoá Gemini |

   Model và provider (`LLM_PROVIDER=ollama`, `LLM_MODEL_*=gemma4:31b`, `EMBEDDING_PROVIDER=gemini`…) đã đặt sẵn
   trong `render.yaml`. Render chỉ áp các giá trị này khi tạo hoặc Sync blueprint; service tạo trước đó cần sửa
   trong Dashboard → Environment.
4. Đợi build xong, mở `https://<service>.onrender.com/api/v1/health`, thấy `{"status":"ok"}` là được.
   Ghi lại URL này cho bước 4.

## 4. Vercel (frontend)

1. Đăng ký [vercel.com](https://vercel.com) bằng GitHub, **Add New → Project**, import repo `meetmind-ai`.
2. **Root Directory**: `frontend`. Framework tự nhận là Next.js, không cần đổi lệnh build.
3. **Environment Variables**:

   | Biến | Giá trị |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | URL Render ở bước 3, không có `/` ở cuối |
   | `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Publishable key của Clerk |
   | `CLERK_SECRET_KEY` | Secret key của Clerk |

4. **Deploy**. Biến `NEXT_PUBLIC_*` được gắn vào lúc build: đổi giá trị thì phải **Redeploy**.

## 5. Nối hai đầu

1. Lấy domain Vercel thật (ví dụ `https://meetmind-ai.vercel.app`).
2. Trên Render, sửa `CLERK_AUTHORIZED_PARTIES` và `CORS_ORIGINS` thành đúng domain đó, lưu lại (Render tự deploy lại).
   Thiếu bước này, trình duyệt báo lỗi CORS hoặc backend trả 401.
3. Instance Development của Clerk chạy được trên domain `vercel.app` (có dòng "Development mode", tối đa 100 user).
   Instance Production của Clerk cần domain riêng của bạn.

## 6. Discord (tuỳ chọn)

1. Trong Discord: Cài đặt kênh → **Tích hợp** → **Webhook** → **Webhook mới** → **Sao chép URL Webhook**.
2. Trên MeetMind: trang **Cài đặt**, dán URL, bật "Bản tin nhắc việc 8h sáng" nếu muốn, **Lưu**, rồi **Gửi thử**.
3. Bản tin 8h sáng cần thêm:
   - Render: `FRONTEND_URL` = URL Vercel, `CRON_SECRET` = một chuỗi ngẫu nhiên dài.
   - GitHub → Settings → Secrets and variables → Actions: `API_URL` = URL Render, `CRON_SECRET` = cùng chuỗi trên.
   - Chạy thử: tab **Actions** → **Daily digest** → **Run workflow**.
   GitHub tự tắt workflow theo lịch nếu repo không có hoạt động trong 60 ngày.

## 7. Bot hỏi đáp Discord (tuỳ chọn)

Bot trả lời lệnh `/hoi <câu hỏi>` trong server Discord giống trang Hỏi đáp. Discord gọi thẳng backend qua
Interactions Endpoint, nên không cần máy chạy bot riêng.

1. [discord.com/developers/applications](https://discord.com/developers/applications) → **New Application**, đặt tên "MeetMind".
2. Trang **General Information**: chép **Application ID** và **Public Key**.
3. Render → Environment: thêm `DISCORD_APP_ID` và `DISCORD_PUBLIC_KEY`, lưu, đợi deploy xong.
4. Vẫn trang General Information, ô **Interactions Endpoint URL** điền
   `https://<service>.onrender.com/api/v1/discord/interactions` → **Save Changes**. Discord gửi thử một request;
   lưu được nghĩa là chữ ký đã khớp. (Render đang ngủ thì lần lưu đầu có thể báo lỗi, đợi 1 phút rồi lưu lại.)
5. Trang **Bot** → **Reset Token** → chép token. Ở máy: thêm `DISCORD_APP_ID` và `DISCORD_BOT_TOKEN` vào `.env`, rồi
   `cd backend && uv run python scripts/register_discord_commands.py` (in ra `Registered: /hoi, /ketnoi`). Token không
   cần đưa lên Render.
6. MeetMind → **Cài đặt** → thẻ **Bot hỏi đáp Discord** (admin): bấm **Mời bot MeetMind**, chọn server.
7. Trong server, người có quyền quản lý server gõ `/ketnoi ma:DC-XXXX-XXXX` (mã ở thẻ trên). Sau đó ai trong server
   cũng gõ được `/hoi`.

Mọi người trong server đã liên kết đều đọc được nội dung các cuộc họp đã phát hành qua bot: chỉ liên kết server dành
riêng cho nhóm. Render Free đang ngủ thì lệnh đầu tiên có thể báo "ứng dụng không phản hồi"; gõ lại sau ít giây.

## Khi nào Render và Vercel deploy lại

- Render chỉ deploy khi commit có thay đổi trong `backend/**` (`buildFilter` trong `render.yaml`; sửa `render.yaml` thì
  bấm **Sync** blueprint trên dashboard để áp dụng, hoặc đặt Settings → Build & Deploy → Build Filters → `backend/**`).
- Vercel bỏ qua build khi không có thay đổi trong `frontend/` (`ignoreCommand` trong `frontend/vercel.json`).
- CI bỏ qua commit chỉ sửa `scripts/**`, `docs/**`, `*.md`, `.gitignore`.

## Kiểm tra sau khi deploy

1. Mở URL Vercel, đăng ký, tạo tổ chức.
2. Tải `evals/datasets/transcripts/payment_v2.txt` lên, người tham gia `Lan | *`, `Minh`, `Hoa`.
3. Đợi phân tích, duyệt, phát hành, rồi hỏi đáp.

Lỗi thường gặp:

| Hiện tượng | Nguyên nhân |
|---|---|
| Lần đầu mở rất chậm | Render Free đang "ngủ", đợi 30–60 giây |
| Lỗi CORS trong console trình duyệt | `CORS_ORIGINS` trên Render chưa đúng domain Vercel |
| 401 khi gọi API | `CLERK_AUTHORIZED_PARTIES`, `CLERK_ISSUER` hoặc `CLERK_JWKS_URL` sai |
| Phân tích đứng ở "Đang chờ" | Worker không kết nối được Redis: kiểm tra `REDIS_URL` (phải là `rediss://`) |
| Log Render báo `sslmode` / `channel_binding` | Đang chạy bản cũ; bản hiện tại tự xử lý URL của Neon |
