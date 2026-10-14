# Xin vào tổ chức bằng mã — design

**Ngày:** 14/10/2026 · **Trạng thái:** đã duyệt trong chat · **Bổ sung cho:** `2026-10-10-meetmind-mvp-design.md`

## Mục tiêu

Người dùng mới không bắt buộc tự tạo tổ chức: họ nhập **mã tham gia** của một tổ chức có sẵn và gửi yêu cầu; admin tổ chức
được báo (chuông trên thanh điều hướng + Discord nếu đã gắn webhook) và đồng ý/từ chối. Đồng ý → backend thêm thành viên
qua Clerk Backend API.

Ngoài phạm vi: đổi vai trò thành viên (đã có trong Clerk: Quản lý tổ chức → Members), tìm tổ chức theo tên.

## Mã tham gia

- Dạng `MM-XXXX-XXXX` (bảng chữ không gây nhầm: bỏ 0/O/1/I/L), lưu ở `org_settings.join_code` (unique). Tạo khi admin xem lần đầu.
- Admin xem `GET /settings/join-code`, đổi `POST /settings/join-code/rotate` (mã cũ hết hiệu lực, yêu cầu đang chờ vẫn giữ).
- Nhập mã không phân biệt hoa thường, bỏ khoảng trắng/gạch.

## Yêu cầu tham gia

Bảng `join_requests(id, org_id, org_name, user_id, user_name, user_email, status, created_at, decided_at, decided_by)`;
`status ∈ pending | approved | rejected | cancelled`. Unique một yêu cầu `pending` cho mỗi (org, user).

Không cần tổ chức đang hoạt động (người xin chưa thuộc tổ chức nào):
- `POST /join-requests {code}` → 201. Mã sai → 404 `invalid_code`. Đã có yêu cầu chờ → 409 `already_requested`.
  Quá 5 yêu cầu đang chờ → 429 `too_many_requests`. Tên/email lấy từ Clerk Backend API (không tin client).
- `GET /join-requests/mine` → các yêu cầu của mình (mới nhất trước).
- `DELETE /join-requests/{id}` → huỷ yêu cầu `pending` của chính mình (của người khác → 404).

Admin của tổ chức đang hoạt động (role `admin`/`org:admin` từ JWT; không phải admin → 403 `admin_only`):
- `GET /join-requests` → yêu cầu `pending` của tổ chức.
- `POST /join-requests/{id}/approve` → Clerk `POST /organizations/{org}/memberships {user_id, role: org:member}`;
  đã là thành viên vẫn tính là thành công. Clerk lỗi → 502 `clerk_error`, yêu cầu vẫn `pending`.
- `POST /join-requests/{id}/reject`.
- Yêu cầu của tổ chức khác → 404; yêu cầu không còn `pending` → 409 `not_pending`.

Thiếu `CLERK_SECRET_KEY` → các thao tác cần Clerk trả 503 `clerk_unavailable`.

## Thông báo

- Discord (best-effort, chạy nền sau khi trả response): "🙋 {tên} ({email}) xin vào tổ chức", link tới `/settings`.
- Chuông trên thanh điều hướng (chỉ admin): số yêu cầu chờ, poll 60 s, bấm vào → `/settings#join-requests`.

## Frontend

- `/select-org`: hai cột — "Tổ chức của bạn" (Clerk `OrganizationList`, gồm cả tạo mới và lời mời) và "Xin vào tổ chức"
  (ô mã, nút gửi, danh sách yêu cầu của mình với trạng thái; được duyệt → nút "Vào tổ chức" gọi `setActive`).
- `/settings` (admin): thẻ "Mã tham gia" (sao chép, đổi mã) và "Yêu cầu tham gia" (Đồng ý / Từ chối). Thành viên thường
  không thấy hai thẻ này.

## Test

- Unit: định dạng/chuẩn hoá mã, Clerk client (MockTransport), role admin từ JWT v1/v2.
- API: luồng gửi → duyệt → Clerk được gọi; từ chối; huỷ; mã sai/đổi mã; trùng; giới hạn 5; non-admin 403; cách ly org
  (admin org A không thấy/duyệt yêu cầu org B → 404); Discord được gọi.
- Vitest: form xin vào, danh sách duyệt.
