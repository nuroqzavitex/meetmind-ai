# Upload audio → transcript (có tách người nói) — design

**Ngày:** 14/10/2026 · **Trạng thái:** đã duyệt trong chat · **Bổ sung cho:** `2026-10-10-meetmind-mvp-design.md`

## Mục tiêu

Người dùng upload file ghi âm cuộc họp thay vì transcript. Hệ thống chuyển giọng nói thành văn bản kèm tách người nói,
người dùng gán tên thật cho từng người nói, rồi luồng phân tích hiện có chạy như với transcript.

Ngoài phạm vi: ghi âm trên trình duyệt, file > 25 MB (cắt nhỏ), nhận diện giọng người đã biết.

## Luồng

```
upload audio (.mp3 .m4a .wav .webm .mp4 .mpeg .mpga, ≤ MAX_AUDIO_BYTES = 25 MB)
  → meeting.status = transcribing, job kind "transcribe"
  → worker: SpeechToText.transcribe → các đoạn (speaker, start, end, text)
  → nhãn chuẩn hoá "Người nói A/B/…" theo thứ tự xuất hiện; ghi transcript dạng txt
    "[HH:MM:SS] Người nói A: …" thay cho audio trong source_filename/source_bytes (audio không giữ lại)
  → meeting.status = awaiting_speakers
  → người dùng gán tên: POST /meetings/{id}/speakers [{label, name, is_decision_maker}]
  → thay nhãn bằng tên trong transcript, context.participants = danh sách gán,
    status analyzing, job "analyze" (pipeline không đổi)
```

## Quyết định

- **Gán tên bằng tay** (đã chọn trong chat): chính xác nhất cho người phụ trách và người có quyền chốt.
- **Transcript sinh ra là file `.txt` chuẩn**: pipeline, phân tích lại, biên bản, hỏi đáp không phải sửa.
- **STT:** OpenAI `gpt-4o-transcribe-diarize`, `response_format="diarized_json"`, `chunking_strategy="auto"`,
  dùng `OPENAI_API_KEY`; model cấu hình bằng `STT_MODEL`. Không có khoá thì job lỗi với thông báo rõ.
- **Phân tích lại** một cuộc họp lỗi: nguồn còn là audio thì chạy lại `transcribe` (về `transcribing`),
  không thì `analyze` như cũ.
- Gán tên chỉ hợp lệ khi `status = awaiting_speakers`; phải gán đủ mọi nhãn, tên không rỗng (≤ 40 ký tự, không chứa `:`),
  tên không trùng nhau. Sai → 422; sai trạng thái → 409.
- Endpoint mới lọc theo org (cross-org → 404) và vào bộ test cách ly.

## API

- `GET /meetings/{id}/speakers` → `[{label, count, samples: [str ≤ 3]}]` (chỉ khi `awaiting_speakers`, khác → 409).
- `POST /meetings/{id}/speakers` body `{speakers: [{label, name, is_decision_maker}]}` → `MeetingCreated` (202).
- `POST /meetings` nhận thêm audio; trả `job_id` của job `transcribe`.
- `MeetingDetail.active_job_id` / `latest_job`: theo job `transcribe` khi status là `transcribing`
  (hoặc khi nguồn còn là audio), còn lại theo `analyze`.

## Frontend

- Form upload nhận audio; chọn audio thì ẩn ô "Người tham gia" (gán ở bước sau), hiện ghi chú.
- Tiến độ job transcribe xong → tự chuyển `/meetings/[id]/speakers`.
- Trang `/meetings/[id]/speakers`: mỗi nhãn một thẻ (số câu, ≤ 3 câu mẫu, ô tên, ô "Người quyết định"), nút "Phân tích".
- Danh sách cuộc họp: nhãn trạng thái "Đang chuyển giọng nói", "Chờ gán người nói"; trạng thái sau có link tới trang gán.

## Test

- Unit: chuẩn hoá nhãn, dựng txt, thay tên, phát hiện audio theo đuôi file.
- Service/API (FakeSTT): upload audio → transcribe → GET speakers → POST speakers → job analyze được tạo; validate 409/422;
  cách ly org cho 2 endpoint mới; phân tích lại khi nguồn là audio.
- Vitest: form upload (audio ẩn người tham gia), trang gán tên.
- Thật (thủ công): file audio nhỏ với `OPENAI_API_KEY`.
