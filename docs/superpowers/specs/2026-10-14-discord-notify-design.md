# Thông báo và nhắc việc qua Discord — design

**Ngày:** 14/10/2026 · **Trạng thái:** đã duyệt trong chat · **Bổ sung cho:** `2026-10-10-meetmind-mvp-design.md`

## Mục tiêu

1. Khi một cuộc họp được phát hành, gửi tóm tắt (quyết định, việc cần làm, số câu hỏi mở, link biên bản) vào kênh Discord của tổ chức.
2. Mỗi sáng 8h (giờ Việt Nam), gửi bản tin nhắc các việc cần làm quá hạn, đến hạn hôm nay và sắp đến hạn.

Ngoài phạm vi: bot Discord (gateway, slash command), tag người dùng Discord, trạng thái "đã xong" cho việc cần làm.

## Cấu hình

- Discord **webhook** (không cần bot). Bảng `org_settings(org_id PK, discord_webhook_url, digest_enabled, updated_at)`.
- URL hợp lệ: `https://discord.com/api/webhooks/<id>/<token>` hoặc `discordapp.com`; khác → 422 `invalid_webhook`.
  Ràng buộc host chống dùng server gửi request tới địa chỉ tuỳ ý.
- API không bao giờ trả URL đầy đủ: chỉ `webhook_hint` (đuôi 4 ký tự).
- Endpoint (lọc theo org, có trong test cách ly — tài nguyên theo org nên không có 404 chéo, test kiểm tra org khác không thấy cấu hình):
  - `GET /settings/discord` → `{configured, webhook_hint, digest_enabled}`
  - `PUT /settings/discord` body `{webhook_url?: str | null, digest_enabled: bool}`; `webhook_url` bỏ qua = giữ nguyên, `null`/`""` = xoá.
  - `POST /settings/discord/test` → gửi tin thử; chưa cấu hình → 409 `not_configured`; Discord lỗi → 502 `discord_error`.
- Mọi thành viên org đều sửa được (chưa có phân quyền admin).

## Thông báo khi phát hành

- Sau `publish` thành công: enqueue job Arq `notify` (best-effort, không tạo hàng `jobs`; lỗi enqueue chỉ log).
- Worker: org không có webhook → bỏ qua. Có → một embed: tiêu đề + ngày; mục **Quyết định**, **Việc cần làm** (`người – nội dung – hạn`), số câu hỏi mở; link `{FRONTEND_URL}/meetings/{id}/minutes`.
- Chỉ mục đã duyệt/đã sửa, không bị thay thế (giống biên bản). Cắt theo giới hạn Discord (field ≤ 1024 ký tự, tối đa ~10 dòng, có "… và N mục khác").
- Discord lỗi/timeout (10 s) → log, không thử lại.

## Bản tin hằng ngày

- `POST /api/v1/internal/digest`, header `X-Cron-Secret` phải khớp `CRON_SECRET`; `CRON_SECRET` rỗng → 503 `digest_disabled`; sai → 401.
- "Hôm nay" theo `Asia/Ho_Chi_Minh`. Với mỗi org có webhook và `digest_enabled`: việc cần làm trong cuộc họp đã phát hành, đã duyệt/sửa, không bị thay thế, có `due_date`:
  - ⚠️ Quá hạn: `today-7 ≤ due < today` (giới hạn 7 ngày vì chưa có trạng thái "đã xong").
  - 📌 Hôm nay: `due = today`. 🗓️ Sắp tới: `today < due ≤ today+2`.
- Không có việc nào → không gửi. Trả `{orgs: n, sent: m}`.
- GitHub Actions `digest.yml`: cron `0 1 * * *` (8h VN) + `workflow_dispatch`, curl có retry (Render free cần ~1 phút thức dậy). Secrets `API_URL`, `CRON_SECRET`; thiếu → bỏ qua.

## Frontend

- Trang `/settings`: ô webhook (type password, placeholder hiện hint khi đã cấu hình), công tắc "Bản tin 8h sáng", nút Lưu, Gửi thử, Xoá webhook. Link "Cài đặt" trên thanh điều hướng.

## Test

- Unit: định dạng embed + cắt; chọn việc theo ngày (biên 7 ngày, +2 ngày, bỏ mục bị từ chối/thay thế); validate URL.
- API (httpx `MockTransport`, không gọi Discord thật): GET/PUT/test, che URL, cách ly org, publish enqueue `notify`, digest secret và nội dung.
- Vitest: trang cài đặt.
