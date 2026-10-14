# Bộ đánh giá MeetMind AI

Dataset tiếng Việt gồm transcript và golden JSON do người gán nhãn (định dạng: `evals/metrics/matching.py`).
Mỗi golden có `context` (kèm `meeting_date`), `topics` (phương án cuối cùng), `items` (theo spec 8.3, 10.1, 10.4, 10.6).
Golden phải được người xác nhận trước khi dùng làm chuẩn (spec 13.2).

## Kịch bản bẫy (`datasets/synthetic/`, kind `trap`)

| File | Họp | Kịch bản và điều kiểm tra |
|---|---|---|
| `a_to_b.txt` | T2 05/10 | Đề xuất A, bị phản đối, chuyển sang B rồi mới chốt. Chỉ B thành quyết định. |
| `b_back_to_a.txt` | T3 06/10 | Chốt A, đổi sang B, mở lại và quay về A. Quyết định cuối là A. |
| `decide_a_then_b.txt` | T4 07/10 | Chốt A, vài phút sau đổi ý chốt B. Chỉ B còn hiệu lực; hạn "ngày dd/mm". |
| `reject_decided.txt` | T5 08/10 | Chốt rồi huỷ quyết định, không có phương án thay: phải ra open_question. |
| `ambiguous_decide.txt` | T6 09/10 | Hai phương án rồi "ok chốt vậy": open_question, không được ra decision. |
| `conditional_decide.txt` | T2 12/10 | Chốt có điều kiện: decision cùng open_question theo dõi điều kiện. |
| `wait_for_boss.txt` | T3 13/10 | "Để em xin ý kiến chị Thảo": open_question và action "Xin ý kiến" của người tự nhận. |
| `joke_hypothetical.txt` | T4 14/10 | Phương án đùa và giả sử không được thành quyết định; hạn "cuối tuần này". |
| `implicit_assignment.txt` | T5 15/10 | "Cái này để em lo", "Để em": người nói tự nhận việc; hạn "trong hôm nay". |
| `relative_deadlines.txt` | T6 16/10 | Năm kiểu hạn: ngày mai, thứ Hai tuần sau, N ngày nữa, cuối tháng, dd/mm. |

## Transcript thực tế (`datasets/transcripts/`, kind `realistic`)

| File | Họp | Nội dung |
|---|---|---|
| `payment_v2.txt` | T5 08/10 | Họp sprint thanh toán: đổi Mongo sang Postgres, blocker, request, knowledge, feedback. |
| `sprint_planning_q4.txt` | T2 19/10 | Sprint planning: đổi OTP từ SMS sang Zalo ZNS, bảng tổng hợp báo cáo, một chủ đề để mở. |
| `customer_meeting_acme.txt` | T4 21/10 | Họp khách hàng: on-premise đổi sang cloud trong nước, ưu tiên Excel thay PDF, câu hỏi mở về QR. |
| `incident_postmortem.txt` | T5 22/10 | Post-mortem sự cố: tăng pool đổi sang PgBouncer, ngưỡng cảnh báo, quy tắc hotfix, feature flag để mở. |
| `hiring_review.txt` | T6 23/10 | Họp tuyển dụng: mời ứng viên rồi đổi thành không mời, offer 30 đổi thành 33 triệu, thử việc để hỏi sếp. |

## Quy ước gán nhãn

- Một quyết định mới rõ ràng (DECIDE) trên một phương án khác thì gán `decision` cho phương án mới (ví dụ `hiring_review`: "chốt không mời Bách").
- Chỉ huỷ quyết định cũ mà không chốt phương án thay thế, khiến chủ đề còn bỏ ngỏ, thì gán `open_question` và không có `decision` (ví dụ `reject_decided`).
- Phương án bị thay thế hoặc bị huỷ không sinh mục nào.
- Mỗi topic có `match` (từ khoá câu hỏi và tên các phương án, để nhận ra mọi decision của topic) và `final_match` (chỉ từ khoá của phương án cuối; bắt buộc khi `final_option` khác null). Topic đúng khi có đúng một decision FINAL khớp `match` và phần phương án (sau "→") của nó khớp `final_match`.
- `match` của item `decision` chỉ chứa từ của phương án (so với phần sau "→"), để decision của phương án bị thay thế không khớp được item gold.

## Chạy đánh giá

Dùng đúng provider và model của app (`LLM_PROVIDER`, `LLM_MODEL_*` trong `.env`): `anthropic` cần `ANTHROPIC_API_KEY`, `openai` cần `OPENAI_API_KEY`.

```
cd backend && PYTHONPATH=.. uv run python -m evals.runners.run_pipeline
```

Tuỳ chọn: `--only <tên>`, `--kind trap|realistic`. Ngưỡng nằm ở `evals/config.yaml`.
Kiểm tra cấu trúc dataset (không cần khoá API): `cd backend && uv run pytest -c pyproject.toml ../tests/backend/unit/test_eval_datasets.py`.

## Đánh giá hỏi đáp (QA)

`datasets/qa/questions.json` gồm 18 câu hỏi tiếng Việt: `answer` (trích dẫn đúng câu nói), `latest` (phương án cuối sau khi đổi ý, lấy từ kịch bản bẫy và transcript thực tế) và `refusal` (thông tin không có trong cuộc họp, phải từ chối).

Quy ước gán nhãn: `meetings` là tên golden (tên file trong `evals/golden/`, bỏ đuôi `.json`); runner lấy transcript và `MeetingContext` từ golden đó. `expect_quote_contains`: trích dẫn trả về phải chứa một trong các chuỗi này (không phân biệt hoa thường) và chuỗi phải có thật trong transcript. `expect_answer_contains` (chỉ `latest`): câu trả lời phải nêu phương án hiện hành. Câu `refusal` không có kỳ vọng và phải trả đúng câu từ chối, không kèm trích dẫn. Mọi câu hỏi dùng chung một tổ chức `eval_org` chứa các cuộc họp được liệt kê.

Cần `ANTHROPIC_API_KEY` và Postgres (`TEST_DATABASE_URL`, tên DB phải kết thúc bằng `_test`; runner xoá và dựng lại schema):

```
docker compose up -d db
cd backend && PYTHONPATH=.. uv run python -m evals.runners.run_qa
```

Tuỳ chọn: `--only <id câu hỏi>`, `--embedder local|hash` (mặc định `local`, BAAI/bge-m3; `local` cần `uv sync --extra embeddings` trong `backend/`). Ngưỡng nằm ở mục `qa_thresholds` trong `evals/config.yaml`. Báo cáo ghi vào `evals/reports/qa-<thời gian>.json`.

| Ngày | Prompt version | Embedder | Citation acc | Latest-state acc | Refusal acc |
|---|---|---|---|---|---|
| chưa chạy | | | | | |

Ngưỡng cần đạt: citation ≥ 0.85, latest-state = 1.00, refusal = 1.00.

## Kết quả

Phân tích từng tình huống: [docs/test-cases.md](../docs/test-cases.md). Báo cáo đầy đủ: `evals/results/`.

| Ngày | Prompt version | Model | Final-decision acc | P | R | Owner+due | Evidence | Trap |
|---|---|---|---|---|---|---|---|---|
| 14/10/2026 | v1 | gpt-4o-mini (arbitrate: gpt-5-mini) | 0.73 | 0.61 | 0.63 | 0.78 | 1.00 | 0.70 |

Ngưỡng cần đạt: P ≥ 0.85, R ≥ 0.75, final-decision ≥ 0.90, owner+due ≥ 0.85, evidence = 1.00, trap = 1.00.
