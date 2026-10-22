# Frontend (Next.js 15 + Clerk)

## Chạy local

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000   (hoặc: make fe-dev)
```

Chạy local (`npm run dev`) đọc biến môi trường từ `frontend/.env.local` (sao chép từ `frontend/.env.example`); `.env` ở thư mục gốc chỉ dùng cho `docker compose` (xem `.env.example` ở gốc):

| Biến | Ghi chú |
|---|---|
| `NEXT_PUBLIC_API_URL` | URL backend mà **trình duyệt** gọi trực tiếp, mặc định `http://localhost:8000` |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Publishable key của Clerk (cần cả lúc build) |
| `CLERK_SECRET_KEY` | Secret key của Clerk (chỉ runtime phía server) |

Các biến `NEXT_PUBLIC_*` được nhúng lúc build: đổi giá trị thì phải build lại (`docker compose up -d --build`). URL đăng nhập/đăng ký (`/sign-in`, `/sign-up`) được gắn cứng trong code, không cần biến môi trường.

Backend phải đang chạy (`make up` hoặc `make db && make api`); `CORS_ORIGINS` và
`CLERK_AUTHORIZED_PARTIES` của backend phải chứa `http://localhost:3000`.

## Cấu hình Clerk

Xem [README → Cấu hình Clerk](../README.md#cấu-hình-clerk). Frontend cần `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
và `CLERK_SECRET_KEY`; người dùng chưa có organization đang active bị chuyển tới `/select-org`.
Admin của org (`membership.role === "org:admin"`, hook `useIsOrgAdmin`) thấy thêm mã tham gia, yêu cầu tham gia, chuông
🔔 trên thanh điều hướng và form sửa cài đặt Discord; thành viên thường chỉ thấy bản xem.

## Sinh lại type API

Type lấy từ OpenAPI của backend (`frontend/openapi.json`) sang `src/types/api.ts`:

```bash
make types         # cd frontend && npm run gen:types
```

Không viết tay lại model của backend; alias nằm ở `src/lib/types.ts`.

## Test

```bash
make fe-test       # eslint + tsc + vitest
make test          # backend pytest rồi fe-test
```

Test nằm ở `frontend/tests/`, không gọi mạng hay Clerk thật (mock `@clerk/nextjs` và `apiFetch`).

## Build / Docker

Build cần publishable key (dùng key giả khi chỉ kiểm tra build):

```bash
cd frontend
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_ZXhhbXBsZS5jbGVyay5hY2NvdW50cy5kZXYk \
CLERK_SECRET_KEY=sk_test_dummy npm run build
```

`docker compose up -d --build` chạy thêm service `frontend` (cổng 3000, `output: "standalone"`,
`node server.js`). `NEXT_PUBLIC_*` được nhúng lúc build qua build args; mặc định API là
`http://localhost:8000` (trình duyệt gọi backend trực tiếp nên phải là URL nhìn thấy từ máy host).
`CLERK_SECRET_KEY` lấy từ biến môi trường / `.env` ở thư mục gốc lúc chạy (compose chỉ truyền biến này vào container).

## Routes

| Route | Mô tả |
|---|---|
| `/` | Danh sách cuộc họp |
| `/meetings/new` | Tạo cuộc họp, upload transcript hoặc file ghi âm |
| `/meetings/[id]/speakers` | Gán tên thật và người quyết định cho từng người nói sau khi chuyển ghi âm thành văn bản |
| `/meetings/[id]/review` | Duyệt các item AI trích xuất |
| `/meetings/[id]/minutes` | Biên bản đã phát hành / xuất |
| `/qa` | Hỏi đáp trên các cuộc họp đã phát hành, kèm chip trích dẫn |
| `/overview` | Tổng hợp: chương trình họp kế tiếp (sao chép, gửi Discord), việc của tôi (nhớ tên đã chọn trong localStorage), sổ quyết định; lọc theo dự án |
| `/sign-in`, `/sign-up` | Đăng nhập / đăng ký (Clerk) |
| `/settings` | Cài đặt: Discord (webhook, bản tin 8h sáng, link mời server; thành viên chỉ xem), bot `/hoi`, mã tham gia và yêu cầu tham gia (admin) |
| `/select-org` | Chọn hoặc tạo organization, hoặc xin vào organization có sẵn bằng mã tham gia |

Thanh điều hướng có thêm nút **Discord** (khi admin đã dán link mời server) và chuông yêu cầu tham gia (admin).

## Deploy

Vercel, Root Directory `frontend`. `frontend/vercel.json` có `ignoreCommand`: Vercel bỏ qua build khi commit không đổi
gì trong `frontend/`. Hướng dẫn: [deploy.md](deploy.md).
