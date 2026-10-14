# Bot hỏi đáp trên Discord — design

**Ngày:** 14/10/2026 · **Trạng thái:** đã duyệt trong chat · **Bổ sung cho:** `2026-10-14-discord-notify-design.md`

## Mục tiêu

Trong server Discord đã liên kết với một tổ chức, gõ `/hoi <câu hỏi>` → bot trả lời công khai trong kênh, giống trang
Hỏi đáp (cùng `services/qa.ask`: chỉ cuộc họp đã phát hành của tổ chức, trích dẫn, câu từ chối cố định).

Ngoài phạm vi: liên kết tài khoản Discord ↔ MeetMind (mọi người trong server đã liên kết đều hỏi được — đã chấp nhận),
hội thoại nhiều lượt, DM.

## Kiến trúc

- **Interactions Endpoint** (HTTP, không gateway): Discord gửi `POST /api/v1/discord/interactions`. Không qua Clerk.
- Xác thực chữ ký Ed25519 (`X-Signature-Ed25519`, `X-Signature-Timestamp`, `DISCORD_PUBLIC_KEY`) trên body thô;
  sai → 401 (Discord yêu cầu). Thiếu cấu hình → 503.
- `PING` (type 1) → `{"type": 1}`.
- `/hoi`: trả ngay type 5 (deferred, công khai), chạy nền: `qa.ask` với `Principal(user_id="discord:<id>", org_id)`
  rồi `PATCH /webhooks/{application_id}/{token}/messages/@original` (token tương tác, không cần bot token).
  Lỗi AI → sửa tin thành thông báo lỗi tiếng Việt.
- `/ketnoi <mã>`: chỉ người có quyền Administrator hoặc Manage Server (bitfield `member.permissions`, kiểm tra ở server)
  → `org_settings.discord_guild_id = guild_id`. Trả lời ẩn (flags 64). Một server ↔ một tổ chức; liên kết lại từ
  tổ chức khác thì chuyển sang tổ chức mới (người làm phải có cả mã của tổ chức mới và quyền quản lý server).
- Lệnh ở server chưa liên kết / ngoài server → trả lời ẩn hướng dẫn.

## Cấu hình

- Render: `DISCORD_APP_ID`, `DISCORD_PUBLIC_KEY` (bắt buộc), `DISCORD_BOT_TOKEN` (chỉ để đăng ký lệnh).
- Đăng ký lệnh một lần: `cd backend && uv run python scripts/register_discord_commands.py` (đọc `.env`).
- Mã liên kết: `org_settings.discord_link_code` (`DC-XXXX-XXXX`), khác mã tham gia.

## API cho admin (`/settings/discord-bot`, chỉ admin)

- `GET` → `{available, linked, link_code, install_url}`; `available=false` khi backend thiếu `DISCORD_APP_ID`/`PUBLIC_KEY`.
- `POST /rotate-code`, `POST /unlink`.

## Tin trả lời

Embed: câu hỏi (tiêu đề), câu trả lời (mô tả, ≤ 4000 ký tự), mục "Nguồn" mỗi trích dẫn
`[n] Tiêu đề · dd/mm/yyyy · hh:mm:ss · người nói — "trích dẫn"` kèm link biên bản; `allowed_mentions` rỗng.

## Test

Unit: chữ ký (khoá Ed25519 sinh trong test), định dạng embed, quyền. API: ping, chữ ký sai, `/ketnoi` (quyền, mã sai,
thành công), `/hoi` (chưa liên kết, đã liên kết → deferred + PATCH chứa câu trả lời, lỗi AI), API admin + cách ly org.
