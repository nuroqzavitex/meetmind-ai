# MeetMind AI — Đặc tả thiết kế MVP (v3)

> Phiên bản v3 · 10/10/2026 · Như Văn Hùng
> v3 thay `MVP_Spec.md` (v2). Thay đổi so với v2:
> - Thêm **đăng nhập bằng Clerk** và **dữ liệu theo nhóm (Clerk Organizations)**; mọi truy vấn lọc theo `org_id`.
> - Phạm vi đợt này: **P0 + Hỏi đáp**. **Bỏ STT** (Agent 0, trang `/transcribe`): input luôn là transcript có sẵn.
> - Sửa máy trạng thái (REJECT sau DECIDE, DECIDE không có option, thứ tự cùng mốc thời gian, đề xuất lại phương án đã bị thay thế); bộ unit test tăng lên 12.
> - Trích dẫn gắn với `utterance_id`; kiểm tra trích dẫn chạy ngay sau extract.
> - Hạn chót tương đối tính bằng code (parser tiếng Việt), không do LLM tính.
> - Ngưỡng `low_confidence` 0.6, hệ số phạt người chốt không có thẩm quyền ×0.85.
> - Đặc tả chi tiết Agent 6 (hỏi đáp): truy vấn lai vector + trigram, RRF, kiểm tra trích dẫn sau sinh.

---

## 0. Bối cảnh, mục tiêu & định nghĩa "xong"

**Bối cảnh:** bài thực hành thể hiện kỹ năng theo đề của nhà tuyển dụng. Người đánh giá sẽ đọc code, chạy thử và xem demo. Ưu tiên: đúng ở bài toán cốt lõi, kiến trúc rõ ràng, có test và eval, README dễ theo. Được phép dùng API LLM bên ngoài.

**Mục tiêu:** từ transcript của một cuộc họp, hệ thống tạo danh sách mục có cấu trúc với đúng **trạng thái cuối**: đề xuất A, cuối buổi chốt B thì B là quyết định, A bị thay thế. Mỗi mục kèm bằng chứng truy được về câu nói gốc; một thành viên trong nhóm duyệt trước khi phát hành. Các cuộc họp đã phát hành tạo thành kho tri thức chung của nhóm để hỏi đáp có trích dẫn.

**MVP xong khi:**

- [ ] Đăng nhập bằng Clerk; người dùng thuộc một org; dữ liệu của org này không bao giờ lộ sang org khác (có test).
- [ ] Upload transcript → màn hình duyệt hiển thị 7 loại mục, mỗi mục có trích dẫn và mốc thời gian.
- [ ] Mọi kịch bản bẫy (A→B, chốt A rồi đổi B, quay lại A, mở lại, bác phương án đã chốt, chốt không rõ phương án, chờ cấp trên) cho ra đúng trạng thái cuối.
- [ ] Duyệt xong thì phát hành được, tải được biên bản `.md` và `.json`.
- [ ] Hỏi đáp trên các cuộc họp đã phát hành của org, câu trả lời có trích dẫn; câu hỏi ngoài dữ liệu trả "không đủ thông tin".
- [ ] `evals/` chạy được và đạt ngưỡng ở mục 13.
- [ ] CI xanh; README đủ để người khác tự dựng và chạy.

---

## 1. Phạm vi

| Mức | Phạm vi | Trạng thái |
|---|---|---|
| **P0** | Đăng nhập + org; transcript → gán nhãn hành vi → máy trạng thái → kiểm tra bằng chứng → màn hình duyệt → phát hành, xuất `.md` + `.json` | **Làm đợt này** |
| **P1** | Hỏi đáp tri thức có trích dẫn | **Làm đợt này** |
| P1 | Chuyển giọng nói (WhisperX + pyannote, trang `/transcribe`) | Không làm (input là transcript) |
| P2 | Jira/Notion/Slack/Discord, agenda họp sau, nối quyết định xuyên cuộc họp, phát hiện mâu thuẫn với quyết định cũ, bot họp thời gian thực, nhắc duyệt qua chat | Không làm |

**Ngoài phạm vi:** phân quyền theo vai trò trong org, hỏi đáp nhiều lượt, streaming câu trả lời, voiceprint, phân tích cảm xúc, đánh giá hiệu suất cá nhân.

---

## 2. Luồng người dùng & đầu ra

```
[/sign-in] ─► [/select-org] (bắt buộc có org đang hoạt động)

[/meetings/new]   transcript + ngữ cảnh ─► job analyze ─► [/meetings/:id/review]
                                                          │ chấp nhận / sửa / bác
                                                          ▼ Phát hành ─► job index
                                      [/meetings/:id/minutes]  xem + tải .md/.json, "Báo sai"
                                      kho tri thức của org ─► [/qa]  hỏi đáp có trích dẫn
```

| Đầu ra | Nội dung |
|---|---|
| Màn hình duyệt | Mục theo 7 loại; trạng thái, độ tin cậy, cờ cảnh báo; bấm vào mục là cuộn tới câu gốc; tab **Diễn biến chủ đề** cho thấy A bị thay thế bởi B lúc nào |
| Biên bản | Markdown + JSON (`MeetingItem[]`), chỉ gồm mục đã duyệt |
| Hỏi đáp | Câu trả lời kèm `[cuộc họp · hh:mm:ss · người nói]`, bấm mở đúng câu gốc |

---

## 3. Tech stack

| Lớp | Chọn | Ghi chú |
|---|---|---|
| Backend | **Python 3.11+**, **uv** | |
| API | **FastAPI** + **Pydantic v2** | OpenAPI → sinh type cho frontend |
| ORM / migration | **SQLAlchemy 2.0 async** + **Alembic** | |
| CSDL | **PostgreSQL 16 + pgvector + pg_trgm** | vector + tìm theo từ khoá trong cùng câu SQL |
| Hàng đợi job | **Arq + Redis** | jobs `analyze`, `index` |
| Xác thực | **Clerk** (`@clerk/nextjs`; backend xác thực JWT qua JWKS bằng `PyJWT`) | Clerk Organizations cho dữ liệu theo nhóm |
| LLM | Wrapper `ai/llm/` gọi **Claude** (Anthropic API), bắt buộc structured output từ schema Pydantic | Model cấu hình theo agent; provider OpenAI để chỗ sẵn |
| Điều phối agent | **LangGraph** (StateGraph) | rẽ nhánh chạy lại, cập nhật tiến trình theo node |
| Embedding | **BAAI/bge-m3** (1024 chiều) qua sentence-transformers, chạy trong worker | sau interface `Embedder` |
| So khớp trích dẫn | **rapidfuzz** | |
| Frontend | **Next.js (App Router) + TypeScript**, **Tailwind + shadcn/ui**, **TanStack Query** | |
| Type FE/BE | **openapi-typescript** → `src/types/api.ts` | |
| Test | **pytest + pytest-asyncio**, **Vitest + Testing Library**, **Playwright** | |
| Theo dõi LLM | **Langfuse** (tuỳ chọn, mặc định tắt) + log có cấu trúc | |
| Dev / CI | Docker Compose, ruff, mypy, ESLint, pre-commit, GitHub Actions | |

---

## 4. Kiến trúc hệ thống

```
 Next.js + Clerk (frontend)
     │  REST, Authorization: Bearer <Clerk session JWT>, poll trạng thái job
     ▼
 FastAPI (backend/app/api)
     │  get_principal() ─► Principal{user_id, org_id, name}
     │  endpoints → services → repositories(org_id bắt buộc) / ai
     │
     ├──► PostgreSQL + pgvector + pg_trgm
     └──► Redis ◄── Arq worker (analyze, index) ──► ai/pipeline ──► Claude API
```

**Quy tắc phụ thuộc:** `endpoints → services → repositories / ai`. Endpoint không gọi thẳng agent; `ai/` không biết gì về HTTP, Clerk hay org. Cùng một lõi chạy từ API, worker và CLI eval.

---

## 5. Xác thực & dữ liệu theo org

### 5.1 Frontend
- `@clerk/nextjs`; `middleware.ts` bảo vệ mọi route trừ `/sign-in`, `/sign-up`.
- Tắt personal account trong Clerk; người dùng chưa có org đang hoạt động bị chuyển tới `/select-org` (`<OrganizationList>` / tạo org). Header có `<OrganizationSwitcher>`.
- `lib/api-client.ts` lấy token bằng `getToken()` và gắn `Authorization: Bearer`. Đổi org thì xoá cache TanStack Query.

### 5.2 Backend
- `app/core/auth.py`: `get_principal()` (FastAPI dependency)
  - Xác thực chữ ký JWT bằng JWKS của Clerk (cache khoá, tải lại khi gặp `kid` lạ), kiểm `exp`, `nbf`, `iss`, và `azp` nằm trong `CLERK_AUTHORIZED_PARTIES`.
  - Lấy `user_id` = `sub`; `org_id` từ claim org (session token v2: `o.id`; v1: `org_id`, hỗ trợ cả hai).
  - Tên hiển thị lấy từ claim tuỳ biến `name` (cấu hình session token trong Clerk Dashboard: `{"name": "{{user.full_name}}"}`); thiếu thì dùng `user_id`.
  - Không có token / token sai → 401. Không có org → 403.
- **Cách ly theo org tại repository:** mọi hàm repository của bảng gốc (`meetings`, `jobs`, `items`, `transcript_chunks`) nhận `org_id` làm tham số bắt buộc. Các bảng con (`utterances`, `dialogue_acts`, `topics`, `item_events`) chỉ được truy cập qua một meeting đã được kiểm tra thuộc org.
- Truy cập tài nguyên của org khác trả **404**, không phải 403.
- Payload job Arq luôn mang `org_id`; worker dùng chính các repository trên.
- Không có bảng `users`: Clerk là nguồn sự thật. `item_events` lưu `actor_id` + `actor_name` (bản sao tại thời điểm thao tác).

### 5.3 Quy tắc duyệt (thay mục 9.2–9.3 của v2)
- Mọi thành viên của org đều duyệt, sửa, phát hành, báo sai được; mọi thao tác ghi vào `item_events`.
- Biên bản **không bao giờ tự phát hành**; chưa phát hành thì meeting ở `in_review`.
- Sửa `status` hoặc `content` của một `decision` sang phương án **khác** phương án trong bằng chứng thì bắt buộc nhập `reason`.
- Sau phát hành, "Báo sai" tạo event `reported`; thành viên có thể mở lại mục (`reopened`), sửa và phát hành lại; mục đó được lập chỉ mục lại.
- Bản sửa chỉ dùng làm few-shot / dữ liệu eval sau khi được xác nhận thủ công.
- Danh sách người tham gia cuộc họp là tên trong transcript, không liên kết với tài khoản Clerk.

---

## 6. Cấu trúc thư mục

```
meetmind-ai/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/v1/endpoints/      # meetings, items, jobs, qa, health
│   │   ├── core/                  # config (pydantic-settings), logging, auth.py
│   │   ├── db/                    # session, base
│   │   ├── models/                # ORM
│   │   ├── schemas/               # DTO request/response
│   │   ├── repositories/          # luôn nhận org_id
│   │   ├── services/              # meeting, review, publish, export, qa
│   │   ├── workers/               # arq: analyze, index
│   │   └── ai/
│   │       ├── domain/            # models.py, enums.py, state_machine.py, due_dates.py
│   │       ├── parsing/           # txt, srt, vtt, docx → Utterance[]
│   │       ├── agents/            # normalize, extract, topics, arbitrate, validate, publish, qa
│   │       ├── pipeline.py        # LangGraph StateGraph
│   │       ├── llm/               # client.py, fake.py, providers/{anthropic,openai}.py
│   │       ├── retrieval/         # embedder.py, search.py
│   │       └── prompts/           # extract/v1.md, topics/v1.md, arbitrate/v1.md, qa_filter/v1.md, qa/v1.md
│   ├── alembic/
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/                   # routes (mục 12)
│   │   ├── features/              # meetings, review, minutes, qa
│   │   ├── components/ui/         # shadcn
│   │   ├── lib/                   # api-client.ts, format.ts
│   │   ├── middleware.ts          # Clerk
│   │   └── types/api.ts           # sinh tự động
│   ├── package.json
│   └── Dockerfile
├── tests/
│   ├── backend/{unit,integration,api}/
│   ├── frontend/
│   ├── e2e/
│   └── fixtures/                  # transcript ngắn, phản hồi FakeLLM, khoá JWT test
├── evals/
│   ├── datasets/{transcripts,synthetic,qa}/
│   ├── golden/
│   ├── metrics/
│   ├── runners/
│   ├── config.yaml
│   └── reports/                   # gitignore
├── docs/superpowers/specs/
├── docker-compose.yml
├── Makefile
├── .env.example
└── README.md
```

---

## 7. Data model

### 7.1 Domain model (`backend/app/ai/domain/models.py`)

```python
from datetime import date
from enum import Enum
from pydantic import BaseModel, Field

class Participant(BaseModel):
    name: str
    role: str | None = None
    is_decision_maker: bool = False

class MeetingContext(BaseModel):
    meeting_id: str
    title: str
    meeting_date: date
    project: str | None = None
    organizer: str | None = None
    participants: list[Participant] = []
    glossary: list[str] = []

class Utterance(BaseModel):
    id: str                               # "u0042"
    seq: int                              # thứ tự trong transcript, bắt đầu từ 0
    speaker: str
    start: float                          # giây
    end: float | None = None
    text: str

class Act(str, Enum):
    PROPOSE = "propose"; SUPPORT = "support"; OBJECT = "object"; AMEND = "amend"
    DECIDE = "decide"; REJECT = "reject"; DEFER = "defer"; REOPEN = "reopen"
    ASSIGN = "assign"; ACCEPT_TASK = "accept_task"
    RAISE_BLOCKER = "raise_blocker"; REQUEST = "request"; FEEDBACK = "feedback"
    KNOWLEDGE = "knowledge"; ASK = "ask"; HYPOTHETICAL = "hypothetical"

class DialogueAct(BaseModel):
    id: str
    utterance_id: str                     # LLM phải trả về đúng id câu được gán
    seq: int                              # sao từ Utterance.seq (code điền, không do LLM)
    speaker: str
    start: float
    act: Act
    quote: str                            # NGUYÊN VĂN, là đoạn con của câu utterance_id
    topic_hint: str | None = None
    topic_id: str | None = None           # do bước topics gán
    option: str | None = None
    content: str | None = None
    assignee: str | None = None
    due_text: str | None = None           # LLM chỉ trích chữ; due_date do code tính
    due_date: date | None = None
    condition: str | None = None
    confidence: float = Field(ge=0, le=1, default=0.7)

class ItemType(str, Enum):
    DECISION = "decision"; ACTION_ITEM = "action_item"; BLOCKER = "blocker"
    REQUEST = "request"; FEEDBACK = "feedback"; OPEN_QUESTION = "open_question"
    KNOWLEDGE = "knowledge"

class ItemStatus(str, Enum):
    FINAL = "final"; SUPERSEDED = "superseded"; REJECTED = "rejected"; OPEN = "open"

class ReviewState(str, Enum):
    PENDING = "pending"; APPROVED = "approved"; EDITED = "edited"; REJECTED = "rejected"

class Evidence(BaseModel):
    utterance_id: str
    speaker: str
    ts: str                               # "00:47:12"
    quote: str

class MeetingItem(BaseModel):
    id: str
    meeting_id: str
    type: ItemType
    topic_id: str | None = None
    content: str
    status: ItemStatus = ItemStatus.FINAL
    supersedes: list[str] = []
    superseded_by: str | None = None
    rationale: str | None = None
    owner: str | None = None
    requester: str | None = None
    due_date: date | None = None
    due_text: str | None = None
    condition: str | None = None
    confidence: float = 0.7
    flags: list[str] = []
    evidence: list[Evidence]
    review_state: ReviewState = ReviewState.PENDING
```

### 7.2 Bảng PostgreSQL

| Bảng | Cột chính | Ghi chú |
|---|---|---|
| `meetings` | id, **org_id**, **created_by**, title, meeting_date, project, organizer, context (jsonb), status (`draft` / `analyzing` / `in_review` / `published` / `failed`), published_at | index (org_id, meeting_date) |
| `utterances` | id, meeting_id, seq, speaker, start, end, text | index (meeting_id, seq) |
| `dialogue_acts` | id, meeting_id, utterance_id, act, option, topic_id, payload (jsonb) | xem "Diễn biến chủ đề" và debug |
| `topics` | id, meeting_id, question, history (jsonb), ambiguous_decides (jsonb) | |
| `items` | id, **org_id**, meeting_id, type, status, review_state, data (jsonb), search_text, embedding vector(1024), indexed_at | HNSW trên embedding; GIN `gin_trgm_ops` trên search_text |
| `item_events` | id, item_id, actor_id, actor_name, action (`created` / `approved` / `edited` / `rejected` / `reported` / `reopened`), before, after, reason, created_at | |
| `transcript_chunks` | id, **org_id**, meeting_id, start_ts, end_ts, first_utterance_id, speakers, text, embedding vector(1024) | cửa sổ 6 câu, chồng lấn 2 câu; HNSW + GIN trigram |
| `jobs` | id, **org_id**, kind (`analyze` / `index`), meeting_id, status (`queued` / `running` / `succeeded` / `failed`), step, progress, error, result (jsonb) | frontend poll |

Chỉ mục chỉ chứa dữ liệu của cuộc họp `published`; khi một mục bị mở lại thì `embedding` của nó bị xoá cho tới khi phát hành lại.

---

## 8. Pipeline & đặc tả agent

### 8.1 Đồ thị LangGraph (job `analyze`)

```
normalize → extract (song song theo đoạn) → check_quotes ─┐
                ▲                                         │ đoạn có > 30% act sai trích dẫn
                └──────── chạy lại đoạn đó, tối đa 1 lần ─┘
→ topics (LLM) → state_machine (code) → arbitrate (LLM, có điều kiện) → build_items
→ validate_fields → persist
```

Mỗi node cập nhật `jobs.step` / `progress`. Lỗi không phục hồi được → `jobs.status = failed` với `error` dễ đọc, meeting chuyển `failed`, người dùng chạy lại được. Lời gọi LLM có retry với backoff cho lỗi tạm thời (429, 5xx, timeout).

### 8.2 Các agent

| Agent | Input → Output | Cách làm | LLM? |
|---|---|---|---|
| 1 · Normalize | file → `Utterance[]` + các đoạn | Parse `.txt` (`[hh:mm:ss] Tên: ...`), `.srt`, `.vtt`, `.docx`; gán `id`, `seq`; sửa thuật ngữ theo glossary (rapidfuzz ≥ 90); chia đoạn 40 câu, chồng lấn 5 câu. File không parse được → lỗi 422 ngay khi upload | Không |
| 2 · Extract | đoạn → `DialogueAct[]` | Structured output; LLM nhận các câu dạng `u0042 [00:47:12] Lan: ...` và phải trả `utterance_id` đúng. Chạy song song các đoạn; loại act trùng ở vùng chồng lấn theo `(utterance_id, act, option)` | Có |
| check_quotes | `DialogueAct[]` → act hợp lệ | `quote` phải khớp với **chính câu `utterance_id`** (`partial_ratio ≥ 90`); act sai bị loại; đoạn có > 30% act sai thì chạy lại Agent 2 cho đoạn đó một lần | Không |
| 3a · Topics | act → act có `topic_id`, option chuẩn hoá | Gom chủ đề; gộp tên gọi khác nhau của cùng phương án ("Mongo" = "MongoDB"); cố gắng gán `option` cho `DECIDE`/`REJECT`/`REOPEN` không có option dựa trên ngữ cảnh | Có |
| 3b · State machine | act theo chủ đề → `Topic[]` | Code thuần, mục 9 | Không |
| 3d · Arbitrate | chủ đề có dấu hiệu mâu thuẫn → kết luận | Chỉ chạy khi có dấu hiệu ở mục 10.1; vẫn mơ hồ → `open_question` + `needs_confirmation` | Có |
| 3c · Build items | `Topic[]` + act → `MeetingItem[]` | Quy tắc ở 8.3; tính `due_date` từ `due_text` (mục 10.6) | Không |
| 4 · Validate | `MeetingItem[]` → mục + flags | Trường bắt buộc, mục trùng, độ tin cậy (mục 10.5) | Không |
| 5 · Publish | mục đã duyệt → `.md`, `.json`; tạo job `index` | Chỉ lấy `approved` / `edited`; meeting → `published` | Không |
| 6 · QA | câu hỏi → câu trả lời + trích dẫn | Mục 11 | Có |

**Model:** cấu hình theo agent trong `config.yaml`/env. Mặc định `claude-sonnet-5-5` cho extract, topics, qa_filter, qa; `claude-opus-5-5` cho arbitrate. Prompt lưu theo phiên bản `ai/prompts/<agent>/vN.md`; phiên bản dùng đặt trong config để eval so sánh được.

### 8.3 Quy tắc sinh mục (3c)

| Nguồn | Mục tạo ra |
|---|---|
| Phương án ở trạng thái `DECIDED` | `decision` (FINAL), `supersedes` = các phương án bị nó thay thế, `rationale` lấy từ SUPPORT/OBJECT, `owner` = người chốt |
| Chủ đề không có phương án nào được chốt | `open_question` |
| `ambiguous_decides` không rỗng | chủ đề có DECIDED → thêm cờ `needs_confirmation` vào `decision`; không có → `open_question` + `needs_confirmation` |
| `DEFER` | `open_question` + `action_item` "xin ý kiến…" nếu có người nhận |
| `DECIDE` có điều kiện | `decision` + `open_question` theo dõi điều kiện |
| Nhóm act giao việc (`ASSIGN`, `ACCEPT_TASK`) | `action_item`; người phụ trách và hạn lấy theo act mới nhất |
| `RAISE_BLOCKER` / `REQUEST` / `FEEDBACK` / `KNOWLEDGE` | `blocker` / `request` / `feedback` / `knowledge` |
| `ASK` không có câu trả lời | `open_question` |
| `HYPOTHETICAL` | bỏ |

---

## 9. Máy trạng thái (`ai/domain/state_machine.py`)

```python
from enum import Enum
from pydantic import BaseModel

class OptState(str, Enum):
    PROPOSED = "proposed"; DISCUSSED = "discussed"; DECIDED = "decided"
    REJECTED = "rejected"; SUPERSEDED = "superseded"; OPEN = "open"

class Option(BaseModel):
    label: str
    state: OptState | None = None
    superseded_by: str | None = None
    decided_act: DialogueAct | None = None
    acts: list[DialogueAct] = []
    history: list[tuple[float, str, str]] = []      # (ts, act, state_after)

class Topic(BaseModel):
    topic_id: str
    question: str
    options: dict[str, Option] = {}
    deferred: bool = False
    ambiguous_decides: list[DialogueAct] = []

DISCUSS = {Act.SUPPORT, Act.OBJECT, Act.AMEND}
INACTIVE = {OptState.REJECTED, OptState.SUPERSEDED}

def _restore_superseded_by(topic: Topic, label: str) -> None:
    for o in topic.options.values():
        if o.superseded_by == label:
            o.state, o.superseded_by = OptState.DISCUSSED, None

def _resolve_option(topic: Topic) -> str | None:
    """DECIDE không có option: chỉ gán khi có đúng một phương án còn hiệu lực."""
    active = [o.label for o in topic.options.values() if o.state not in INACTIVE]
    return active[0] if len(active) == 1 else None

def run_topic(topic: Topic, acts: list[DialogueAct]) -> Topic:
    for a in sorted(acts, key=lambda x: (x.start, x.seq)):
        label = a.option
        if label is None and a.act == Act.DECIDE:
            label = _resolve_option(topic)
            if label is None:
                topic.ambiguous_decides.append(a)
                continue
        if label is None:
            if a.act == Act.DEFER:
                topic.deferred = True
            continue

        opt = topic.options.setdefault(label, Option(label=label))
        opt.acts.append(a)

        if a.act == Act.PROPOSE and opt.state is None:
            opt.state = OptState.PROPOSED
        elif a.act in DISCUSS and opt.state in (None, OptState.PROPOSED):
            opt.state = OptState.DISCUSSED
        elif a.act == Act.DECIDE:
            opt.state, opt.decided_act, opt.superseded_by = OptState.DECIDED, a, None
            for o in topic.options.values():
                if o is not opt and o.state != OptState.REJECTED:
                    o.state, o.superseded_by = OptState.SUPERSEDED, opt.label
        elif a.act == Act.REJECT:
            if opt.state == OptState.DECIDED:
                opt.decided_act = None
                _restore_superseded_by(topic, opt.label)
            opt.state, opt.superseded_by = OptState.REJECTED, None
        elif a.act == Act.REOPEN and opt.state == OptState.DECIDED:
            opt.state, opt.decided_act = OptState.DISCUSSED, None
            _restore_superseded_by(topic, opt.label)
        elif a.act == Act.DEFER:
            topic.deferred = True
        # PROPOSE/SUPPORT/OBJECT/AMEND trên phương án đã SUPERSEDED/REJECTED:
        # chỉ ghi lịch sử, không đổi trạng thái (chỉ DECIDE/REOPEN mới đổi được).

        opt.history.append((a.start, a.act.value, opt.state.value if opt.state else "-"))

    if not any(o.state == OptState.DECIDED for o in topic.options.values()):
        for o in topic.options.values():
            if o.state in (None, OptState.PROPOSED, OptState.DISCUSSED):
                o.state = OptState.OPEN
    return topic
```

**Unit test bắt buộc** (`tests/backend/unit/test_state_machine.py`)

| # | Kịch bản | Chuỗi act | Kỳ vọng |
|---|---|---|---|
| 1 | A→B cơ bản | PROPOSE A, OBJECT A, PROPOSE B, SUPPORT B, DECIDE B | B = DECIDED, A = SUPERSEDED (bởi B) |
| 2 | Chốt A rồi đổi B | PROPOSE A, DECIDE A, PROPOSE B, DECIDE B | B = DECIDED, A = SUPERSEDED |
| 3 | Quay lại A | DECIDE A, DECIDE B, DECIDE A | A = DECIDED, B = SUPERSEDED |
| 4 | Mở lại, không chốt | PROPOSE A, DECIDE B, REOPEN B | A, B = OPEN |
| 5 | Không ai chốt | PROPOSE A, SUPPORT A | A = OPEN → `open_question` |
| 6 | Bác | PROPOSE A, REJECT A, PROPOSE B, DECIDE B | A = REJECTED, B = DECIDED |
| 7 | Hoãn | PROPOSE A, DEFER (không có option) | deferred, A = OPEN |
| 8 | Bác phương án đã chốt | PROPOSE A, DECIDE B, REJECT B | B = REJECTED, A = OPEN, không còn SUPERSEDED |
| 9 | Chốt không rõ phương án, một ứng viên | PROPOSE A, SUPPORT A, DECIDE (option None) | A = DECIDED |
| 10 | Chốt không rõ phương án, nhiều ứng viên | PROPOSE A, PROPOSE B, DECIDE (option None) | A, B = OPEN; `ambiguous_decides` có 1 act |
| 11 | Cùng mốc thời gian | DECIDE A (seq 1), DECIDE B (seq 2), cùng `start` | B = DECIDED, A = SUPERSEDED |
| 12 | Ủng hộ lại phương án đã bị thay thế | DECIDE A, DECIDE B, SUPPORT A | B = DECIDED, A = SUPERSEDED |

---

## 10. Quy tắc nghiệp vụ

### 10.1 Quyết định thật và ý kiến của người có chức vụ cao
- Chức vụ **không** biến ý kiến thành quyết định. Chỉ act `DECIDE` (có tín hiệu chốt rõ) mới tạo quyết định.
- Các câu "hay là…", "em nghĩ…", "chắc là…", "để xem…" không phải `DECIDE`.
- Độ tin cậy của quyết định:

```python
def decision_confidence(opt: Option, ctx: MeetingContext) -> float:
    a = opt.decided_act
    c = a.confidence
    makers = {p.name for p in ctx.participants if p.is_decision_maker}
    if makers and a.speaker not in makers:
        c *= 0.85                                  # người chốt không có thẩm quyền
    if any(x.act == Act.OBJECT and x.start > a.start for x in opt.acts):
        c *= 0.6                                   # có phản đối sau khi chốt
    return round(c, 2)
```

- Gọi arbitrate (3d) khi có một trong các dấu hiệu: hai `DECIDE` khác phương án cách nhau < 60 giây; `DECIDE` từ người không có thẩm quyền rồi có `OBJECT` ngay sau; có `OBJECT` sau `DECIDE` mà không có `REOPEN`. Nếu vẫn mơ hồ: `open_question` + cờ `needs_confirmation`.

### 10.2 Ai duyệt biên bản
Xem mục 5.3: mọi thành viên của org.

### 10.3 Người duyệt sửa sai
Xem mục 5.3.

### 10.4 Tri thức hay chuyện phiếm
- Phép thử trong prompt: *"Một người mới vào dự án 3 tháng sau có cần biết điều này không?"*
- Là tri thức: quy ước, ràng buộc kỹ thuật/kinh doanh, lý do của quyết định, bài học từ sự cố, sự thật về khách hàng hoặc hệ thống.
- Không phải tri thức: cảm xúc, chuyện ngoài lề, trạng thái tạm thời ("staging đang hỏng" là `blocker`).
- Khi phân vân thì **không** tạo mục `knowledge`; người duyệt có thể tự thêm.

### 10.5 Kiểm tra trường bắt buộc (Agent 4)

| Loại | Bắt buộc | Thiếu thì |
|---|---|---|
| decision | owner (người chốt), ≥ 1 evidence | `missing_owner` |
| action_item | owner, due_date | `missing_owner`, `missing_due_date` |
| request | requester | `missing_requester` |
| mọi loại | evidence đã qua check_quotes | mục không còn evidence thì bỏ mục |
| mọi loại | confidence ≥ 0.6 | `low_confidence`, đưa lên đầu màn hình duyệt |

"Chấp nhận mục sạch" chấp nhận mọi mục không có cờ nào.

### 10.6 Hạn chót tương đối (`ai/domain/due_dates.py`)
- LLM chỉ trích `due_text`; hàm thuần `resolve_due(due_text, meeting_date) -> date | None` tính ngày.
- Tuần bắt đầu từ thứ Hai. Mẫu hỗ trợ:
  - "thứ Hai…thứ Bảy / Chủ nhật **tuần này**", "… **tuần sau**";
  - "thứ X" trống: lần gần nhất **sau** ngày họp;
  - "hôm nay", "ngày mai", "ngày kia / ngày mốt", "N ngày nữa";
  - "cuối tuần (này / sau)": thứ Sáu của tuần đó; "cuối tháng": ngày cuối tháng;
  - "dd/mm", "dd/mm/yyyy", "ngày dd": nếu thiếu năm/tháng thì lấy lần gần nhất không trước ngày họp.
- Không khớp mẫu nào → `None` (Agent 4 sẽ gắn `missing_due_date`); "bắt đầu từ tuần sau" là mốc bắt đầu, không phải hạn.
- Ví dụ: họp 08/10/2026 (thứ Năm), "thứ Sáu tuần sau" → 16/10/2026. Có unit test cho từng mẫu.

---

## 11. Hỏi đáp (Agent 6)

### 11.1 Lập chỉ mục (job `index`, sau khi phát hành)
- Mỗi mục `approved` / `edited`: `search_text` = `"<loại>: <nội dung>. Lý do: <rationale>. Phụ trách: <owner>"`; nhúng bằng `Embedder`.
- `transcript_chunks`: cửa sổ 6 câu, chồng lấn 2 câu, mỗi chunk lưu tên người nói và mốc thời gian.
- Mở lại một mục → xoá embedding của mục đó; phát hành lại → chỉ lập chỉ mục lại mục bị đổi.

### 11.2 Trả lời
1. **Tách bộ lọc** (LLM, prompt `qa_filter`): `{project?, date_from?, date_to?, people[], item_types[], rewritten_query}`. LLM nhận danh sách dự án thực của org; dự án ngoài danh sách bị bỏ. `project` gửi từ UI ưu tiên hơn.
2. **Truy vấn lai** (một câu SQL cho mỗi nguồn, luôn lọc `org_id` và meeting `published`):
   - vector: top 20 `items` + top 20 `transcript_chunks` theo cosine;
   - từ khoá: `pg_trgm` (`word_similarity`) trên `search_text` / `text`, top 20 mỗi nguồn;
   - gộp bằng **RRF** (k = 60), giữ 12 ngữ cảnh.
3. **Chuỗi thay thế:** mục trúng có `superseded_by` → đi theo chuỗi tới mục mới nhất (trong cùng cuộc họp), đưa cả hai vào ngữ cảnh, đánh dấu cũ/mới. Ngữ cảnh sắp theo `meeting_date`; prompt yêu cầu coi cuộc họp mới nhất là trạng thái hiện tại và nêu rõ khi có thay đổi. *Nối quyết định xuyên cuộc họp là P2.*
4. **Sinh câu trả lời:** ngữ cảnh được đánh số `[1]…[n]`; LLM chỉ dùng ngữ cảnh, mỗi ý gắn `[n]`; structured output `{answer, used_refs[]}`.
5. **Kiểm tra sau sinh:** bỏ các `[n]` không tồn tại trong ngữ cảnh. Không còn trích dẫn hợp lệ, hoặc truy vấn không có ngữ cảnh nào → trả `"Không đủ thông tin trong các cuộc họp đã phát hành."` với `citations = []`.

### 11.3 Giao diện
- Một lượt hỏi, một câu trả lời (không nhớ hội thoại, không streaming).
- `CitationChip` hiển thị `[tiêu đề · hh:mm:ss · người nói]`, bấm mở `/meetings/[id]/minutes?u=<utterance_id>` và cuộn tới câu gốc.

---

## 12. API & Frontend

### 12.1 API (`/api/v1`, mọi endpoint trừ `/health` yêu cầu Clerk JWT có org)

| Method | Endpoint | Việc |
|---|---|---|
| GET | `/health` | kiểm tra sống |
| POST | `/meetings` | multipart: file transcript + `context` (JSON) → `{meeting_id, job_id}` |
| GET | `/jobs/{id}` | `{status, step, progress, error}` |
| GET | `/meetings` | danh sách của org, lọc theo dự án/trạng thái |
| GET | `/meetings/{id}` | ngữ cảnh + transcript |
| POST | `/meetings/{id}/reanalyze` | chạy lại phân tích khi `failed` |
| GET | `/meetings/{id}/items` | mục cần duyệt (có cờ lên trước) |
| GET | `/meetings/{id}/topics` | diễn biến chủ đề |
| PATCH | `/items/{id}` | `{action: approve\|edit\|reject, patch?, reason?}` |
| POST | `/meetings/{id}/items/approve-clean` | chấp nhận hàng loạt mục không có cờ |
| POST | `/meetings/{id}/publish` | phát hành + tạo job index |
| GET | `/meetings/{id}/export?format=md\|json` | tải biên bản |
| POST | `/items/{id}/report` | báo sai sau phát hành |
| POST | `/items/{id}/reopen` | mở lại mục đã phát hành |
| POST | `/qa` | `{question, project?}` → `{answer, citations[{meeting_id, title, date, ts, speaker, quote, utterance_id}]}` |

Lỗi trả dạng `{"error": {"code", "message"}}`; 401/403/404/409 (ví dụ phát hành khi còn job chạy)/422.

### 12.2 Frontend

| Route | Thành phần chính |
|---|---|
| `/sign-in`, `/sign-up` | Clerk |
| `/select-org` | chọn / tạo org |
| `/` | danh sách cuộc họp của org + trạng thái |
| `/meetings/new` | upload file; form ngữ cảnh (tiêu đề, ngày, dự án, người tham gia + vai trò + "người ra quyết định", glossary); tiến trình theo từng bước |
| `/meetings/[id]/review` | **Hai cột:** trái là tabs 7 loại mục (`ItemCard`: nội dung sửa được, owner, due, badge trạng thái/độ tin cậy/cờ, phương án bị thay thế gạch ngang); phải là `TranscriptPanel` tự cuộn tới câu gốc. Tab **Diễn biến chủ đề** (`TopicTimeline`). Nút "Chấp nhận mục sạch", "Phát hành" |
| `/meetings/[id]/minutes` | biên bản, tải `.md` / `.json`, "Báo sai" / "Mở lại" trên từng mục, `?u=` cuộn tới câu gốc |
| `/qa` | khung hỏi, gợi ý câu hỏi mẫu, `CitationChip` |

Giao diện tiếng Việt. `TopicTimeline` là màn hình đáng đầu tư nhất khi demo.

---

## 13. Test & đánh giá

### 13.1 `tests/` (không bao giờ gọi API thật)
- **Unit:** máy trạng thái (12 ca), `resolve_due`, parser transcript, check_quotes, build_items, validate, RRF, kiểm tra trích dẫn sau sinh.
- **Integration:** pipeline với `FakeLLM` (phản hồi fixture theo prompt) trên `payment_v2.txt`; repository trên Postgres thật (docker).
- **API:** JWT giả lập ký bằng cặp khoá test, JWKS trỏ tới khoá test. **Bộ test cách ly org:** user org X gọi mọi endpoint với id của org Y → 404; `/qa` của org X không bao giờ trích dẫn cuộc họp org Y.
- **Frontend:** Vitest cho `ItemCard`, `TopicTimeline`, `CitationChip`.
- **E2E (Playwright):** đăng nhập test (Clerk testing token) → upload → duyệt → phát hành → tải `.md` → hỏi đáp. Backend chạy với `FakeLLM`.

### 13.2 `evals/` (gọi Claude thật, cho điểm số)

| Chỉ số | Cách đo | Ngưỡng MVP |
|---|---|---|
| Độ chính xác quyết định cuối | % chủ đề mà mục FINAL khớp nhãn | ≥ 0.90 |
| Precision / recall theo loại mục | so khớp mục với golden (tương đồng nội dung + cùng loại) | P ≥ 0.85, R ≥ 0.75 |
| Đúng người phụ trách + hạn chót | % action_item đúng cả hai trường | ≥ 0.85 |
| Bám bằng chứng | % evidence khớp nguyên văn | 1.00 |
| Kịch bản bẫy | % kịch bản synthetic cho đúng trạng thái cuối | 1.00 |
| QA · trích dẫn đúng | % câu trả lời có ít nhất một trích dẫn trỏ đúng câu gốc kỳ vọng | ≥ 0.85 |
| QA · đúng trạng thái mới nhất | % câu hỏi về quyết định đã bị thay thế mà trả lời phương án mới | 1.00 |
| QA · từ chối đúng | % câu hỏi không có đáp án mà trả "không đủ thông tin" | 1.00 |

- **Dataset:** `payment_v2` + bộ synthetic (A→B, B→A, quay lại A, bác phương án đã chốt, chốt không rõ phương án, chốt có điều kiện, chờ cấp trên, đùa/giả định, giao việc ngầm, hạn chót tương đối) + vài transcript thực tế; mục tiêu tổng 15 transcript. Khoảng 15 câu hỏi QA trong `evals/datasets/qa/`.
- **Nguồn dữ liệu:** transcript và golden nháp sinh bằng Claude; **golden phải được người xem lại và xác nhận** trước khi dùng làm ngưỡng.
- **Chạy:** `PYTHONPATH=backend python -m evals.runners.run_pipeline --prompt-version v1` và `... run_qa`.
- **CI:** chạy eval khi PR đụng tới `ai/prompts/` hoặc `ai/agents/`; fail nếu dưới ngưỡng.

---

## 14. Setup

**`docker-compose.yml` (rút gọn)**

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment: { POSTGRES_USER: app, POSTGRES_PASSWORD: app, POSTGRES_DB: meeting }
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
  redis:
    image: redis:7
    ports: ["6379:6379"]
  backend:
    build: ./backend
    command: sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"
    env_file: .env
    depends_on: [db, redis]
    ports: ["8000:8000"]
  worker:
    build: ./backend
    command: arq app.workers.main.WorkerSettings
    env_file: .env
    depends_on: [db, redis]
    volumes: [hf-cache:/root/.cache/huggingface]
  frontend:
    build: ./frontend
    env_file: .env
    ports: ["3000:3000"]
volumes: { pgdata: {}, hf-cache: {} }
```

Migration đầu tiên bật `CREATE EXTENSION vector; CREATE EXTENSION pg_trgm;`.

**`.env.example`**

```
# Backend
DATABASE_URL=postgresql+asyncpg://app:app@db:5432/meeting
REDIS_URL=redis://redis:6379
CLERK_JWKS_URL=https://<your-frontend-api>.clerk.accounts.dev/.well-known/jwks.json
CLERK_ISSUER=https://<your-frontend-api>.clerk.accounts.dev
CLERK_AUTHORIZED_PARTIES=http://localhost:3000
LLM_PROVIDER=anthropic          # anthropic | openai
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
LLM_MODEL_DEFAULT=claude-sonnet-5-5
LLM_MODEL_ARBITRATE=claude-opus-5-5
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024
PROMPT_VERSION=v1
LANGFUSE_HOST=

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
CLERK_SECRET_KEY=
```

**`Makefile`**

```
up:       docker compose up --build
migrate:  cd backend && alembic upgrade head
test:     cd backend && uv run pytest && cd ../frontend && npm run test
e2e:      npx playwright test tests/e2e
eval:     PYTHONPATH=backend python -m evals.runners.run_pipeline && PYTHONPATH=backend python -m evals.runners.run_qa
types:    cd frontend && npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts
```

**Cấu hình test** (vì `tests/` nằm ngoài): `backend/pyproject.toml` đặt `testpaths = ["../tests/backend"]`, `pythonpath = ["."]`; `frontend/vitest.config.ts` đặt `include: ["../tests/frontend/**/*.test.{ts,tsx}"]`.

---

## 15. Kế hoạch triển khai

| Mốc | Việc | Xong khi |
|---|---|---|
| **M1 · Nền** | Repo, docker compose, khung FastAPI + Alembic (extension vector, pg_trgm); `get_principal` + repository lọc org + test cách ly; khung Next.js + Clerk + `OrganizationSwitcher` + `/select-org` | `make up` chạy; đăng nhập được; test cách ly xanh |
| **M2 · Lõi AI** | Domain model; máy trạng thái + 12 test; parser transcript; `resolve_due`; wrapper LLM + `FakeLLM`; agent 1–4, check_quotes, arbitrate; LangGraph pipeline; runner eval với `payment_v2` + kịch bản bẫy | CLI trên `payment_v2.txt` đạt ≥ 8/10 mục khớp golden; kịch bản bẫy 100% |
| **M3 · Duyệt & phát hành** | Worker `analyze`; API meetings/items/jobs/topics; màn hình duyệt, `TranscriptPanel`, `TopicTimeline`; publish + export; báo sai / mở lại | Luồng upload → biên bản chạy được trên trình duyệt |
| **M4 · Hỏi đáp** | Job `index`; truy vấn lai + RRF; Agent 6; trang `/qa`; eval QA; mở rộng dataset lên 15 transcript | Câu hỏi mẫu trả lời đúng, có trích dẫn; câu ngoài dữ liệu trả "không đủ thông tin"; eval đạt ngưỡng |
| **M5 · Hoàn thiện** | Playwright e2e; GitHub Actions (lint, type, test; eval khi đổi prompt/agent); README: sơ đồ kiến trúc, các quyết định thiết kế, bảng kết quả eval, hướng dẫn cấu hình Clerk | CI xanh; người khác tự dựng được theo README |

---

## 16. Dữ liệu mẫu (`evals/datasets/transcripts/payment_v2.txt`)

```
[00:00:05] Lan: Hôm nay mình chốt CSDL cho dịch vụ thanh toán và phân việc sprint tới nhé.
[00:00:20] Minh: Em đề xuất dùng MongoDB cho nhanh, schema linh hoạt.
[00:01:02] Hoa: Mongo thì phần transaction nhiều bảng hơi khó, mình đang cần ACID.
[00:01:40] Minh: Giả sử mình bỏ luôn phần hoàn tiền thì Mongo vẫn ổn mà, đùa thôi.
[00:02:15] Lan: Hay mình dùng Postgres? Team đã quen rồi.
[00:02:40] Minh: Postgres cũng ổn, em đồng ý.
[00:03:05] Hoa: Em cũng thấy Postgres hợp hơn.
[00:03:30] Lan: Vậy mình chốt Postgres nhé. Lưu ý chung: dịch vụ thanh toán bắt buộc giao dịch ACID.
[00:04:10] Lan: Minh dựng schema Postgres, xong trước thứ Sáu tuần sau nhé.
[00:04:20] Minh: Vâng ạ.
[00:04:45] Hoa: Môi trường staging đang hỏng, em chưa test được API cũ.
[00:05:10] Minh: Cái staging để em lo luôn.
[00:05:40] Hoa: Còn có cần replica đọc không chị?
[00:06:00] Lan: Cái này để chị xin ý kiến anh Tuấn rồi báo lại.
[00:06:30] Hoa: Bên CS nhờ mình xuất báo cáo giao dịch lỗi hằng tuần.
[00:07:00] Lan: Ok, Hoa làm báo cáo đó, bắt đầu từ tuần sau. Tài liệu API đợt này viết rõ hơn hẳn, tốt lắm.
```

**Golden** (ngày họp 08/10/2026, thứ Năm; Lan là người ra quyết định), lưu thành `evals/golden/payment_v2.json`:

| Loại | Nội dung | Ghi chú |
|---|---|---|
| decision | Dùng PostgreSQL cho dịch vụ thanh toán | FINAL, owner Lan, supersedes MongoDB, evidence 00:03:30 |
| action_item | Dựng schema Postgres | Minh, due 16/10/2026 ("thứ Sáu tuần sau") |
| action_item | Sửa môi trường staging | Minh tự nhận, cờ `missing_due_date` |
| action_item | Xin ý kiến anh Tuấn về replica đọc | Lan |
| action_item | Xuất báo cáo giao dịch lỗi hằng tuần | Hoa, bắt đầu tuần sau, cờ `missing_due_date` |
| blocker | Staging hỏng, chưa test được API cũ | Hoa nêu |
| request | CS cần báo cáo giao dịch lỗi hằng tuần | requester: CS |
| open_question | Có cần replica đọc không? | chờ anh Tuấn |
| knowledge | Dịch vụ thanh toán bắt buộc giao dịch ACID | |
| feedback | Tài liệu API đợt này viết rõ hơn | tích cực |
| — | "Giả sử bỏ phần hoàn tiền…" | HYPOTHETICAL, không tạo mục |
