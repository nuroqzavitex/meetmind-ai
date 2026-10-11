# E2E (Playwright)

Một test duy nhất (`full-flow.spec.ts`) đi hết luồng chính qua giao diện thật:
đăng nhập Clerk → tải transcript `tests/fixtures/transcripts/payment_v2.txt` → duyệt mọi mục → phát hành →
tải biên bản `.md` → hỏi đáp và bấm citation về đúng biên bản.

Backend và worker chạy với `LLM_PROVIDER=fake` (đọc câu trả lời từ `tests/fixtures/llm/payment_v2`)
và `EMBEDDING_PROVIDER=hash`, nên không gọi Anthropic và không tải model embedding.

## 1. Tạo user test trên Clerk

Dùng instance **development** của Clerk (testing token không chạy với instance production).

1. Clerk Dashboard → **User & Authentication** → bật đăng nhập bằng **Password**
   (và **Username** nếu muốn dùng username làm định danh; email cũng được).
2. **Users** → **Create user**: đặt username (hoặc email) và mật khẩu. Không bật MFA cho user này.
3. **Organizations** → tạo một organization (nếu chưa có) và thêm user test làm thành viên.
   User phải thuộc ít nhất một organization: ngay sau khi đăng nhập, test tự kích hoạt organization đầu tiên
   (session mới có thể ở trạng thái "pending" vì đã tắt Personal accounts). Không có organization nào thì test
   báo lỗi rõ ràng.

## 2. Biến môi trường

`playwright.config.ts` đọc theo thứ tự ưu tiên: biến môi trường thật → `frontend/.env.local` → `.env` ở gốc repo.
Giá trị rỗng bị bỏ qua, nên một dòng `E2E_CLERK_USER_USERNAME=` để trống trong `frontend/.env.local` không che
giá trị ở `.env` gốc.

Nên đặt `E2E_CLERK_USER_USERNAME` / `E2E_CLERK_USER_PASSWORD` ở **một** chỗ: `frontend/.env.local` (mẫu trong
`frontend/.env.example`) hoặc `.env` ở gốc repo. Các biến backend (`CLERK_JWKS_URL`, `DATABASE_URL`...) đọc từ `.env` gốc.

| Biến | Dùng cho |
| --- | --- |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY` | Frontend, và `clerkSetup()` lấy testing token |
| `CLERK_JWKS_URL`, `CLERK_ISSUER` | Backend xác thực JWT |
| `E2E_CLERK_USER_USERNAME`, `E2E_CLERK_USER_PASSWORD` | Đăng nhập user test (username hoặc email) |
| `DATABASE_URL`, `REDIS_URL` | Postgres/Redis đang chạy và đã migrate (`make db && make migrate`), dùng host `localhost` |

Thiếu `CLERK_SECRET_KEY` hoặc `E2E_CLERK_USER_USERNAME` thì test bị **skip** (exit 0) và không khởi động server nào.

`LLM_PROVIDER`, `EMBEDDING_PROVIDER`, `FAKE_LLM_DIR` do config tự đặt cho backend và worker, không cần khai báo.

## 3. Chạy

```bash
make db && make migrate                       # Postgres + Redis
cd frontend && npx playwright install chromium   # lần đầu
make e2e                                      # = cd frontend && npx playwright test
```

Playwright tự khởi động ba tiến trình: backend (`uvicorn`, cổng 8000), worker (`arq`) và frontend
(`npm run dev` ở máy dev; `npm run build && npm run start` khi có `CI`).

**Lưu ý khi chạy ở máy dev:** ngoài CI, server đang chạy sẵn ở cổng 8000/3000 sẽ được dùng lại. Nếu bạn đang
chạy `make api` / `make worker` với LLM thật, hãy tắt chúng trước, nếu không backend/worker cũ sẽ gọi Anthropic
và nhận cả job của test.

Mỗi lần chạy tạo một cuộc họp mới với tiêu đề `E2E payment <timestamp>` và project `e2e-<timestamp>`;
dữ liệu cũ không cần dọn. Khi test lỗi, trace nằm trong `frontend/test-results/`
(`npx playwright show-trace <file>`).
