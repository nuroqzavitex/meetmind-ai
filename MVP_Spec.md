# Trí tuệ cuộc họp — Đặc tả MVP (v2)

> Phiên bản v2 · 10/10/2026 · Như Văn Hùng
> v2 thay bản v1 (bản viết trong đêm 08/10). Thay đổi so với v1:
> - Chuyển từ Streamlit + SQLite sang **FastAPI + Next.js + PostgreSQL/pgvector**.
> - Thêm worker chạy nền, đưa `tests/` và `evals/` ra ngoài thư mục backend.
> - Bổ sung các quy tắc nghiệp vụ đã chốt khi phản biện.

---

## 0. Mục tiêu & định nghĩa "xong"

**Mục tiêu:** từ transcript (hoặc audio) của một cuộc họp, hệ thống tạo ra danh sách mục có cấu trúc với đúng **trạng thái cuối**: đề xuất A, cuối buổi chốt B thì B là quyết định, A bị thay thế. Mỗi mục kèm bằng chứng truy được về câu nói gốc, và người chủ trì duyệt trước khi phát hành.

**MVP xong khi:**

- [ ] Upload transcript → màn hình duyệt hiển thị 7 loại mục, mỗi mục có trích dẫn và mốc thời gian.
- [ ] Mọi kịch bản bẫy (A→B, chốt A rồi đổi B, mở lại, chờ cấp trên) cho ra đúng trạng thái cuối.
- [ ] Duyệt xong thì phát hành được, tải được biên bản `.md` và `.json`.
- [ ] Hỏi đáp trên các cuộc họp đã phát hành, câu trả lời có trích dẫn.
- [ ] Upload audio → transcript có tách người nói, tải về được mà không cần chạy phân tích.
- [ ] `evals/` chạy được và đạt ngưỡng ở mục 12.

---

## 1. Phạm vi

| Mức | Phạm vi | Vì sao ở mức này |
|---|---|---|
| **P0** | Transcript → gán nhãn hành vi → máy trạng thái → kiểm tra bằng chứng → màn hình duyệt → phát hành, xuất `.md` + `.json` | Trả lời trực tiếp câu hỏi cốt lõi của đề. Trạng thái cuối mà sai thì mọi thứ phía sau sai theo |
| **P1** | Hỏi đáp tri thức có trích dẫn; công cụ chuyển giọng nói độc lập | Dùng lại dữ liệu P0; mở rộng nguồn đầu vào |
| **P2** | Tích hợp Jira/Notion/Slack/Discord, agenda cho họp sau, nối quyết định xuyên cuộc họp, bot họp thời gian thực | Chỉ đáng làm khi P0 đã đạt ngưỡng đánh giá |

**Ngoài phạm vi MVP:** đăng nhập nhiều tổ chức, voiceprint, phân tích cảm xúc, đánh giá hiệu suất cá nhân.

---

## 2. Luồng người dùng & đầu ra

```
[/transcribe]      audio ─► job STT ─► transcript (.txt/.srt) ─► tải về   (dừng ở đây được)

[/meetings/new]    transcript|audio + ngữ cảnh ─► job phân tích ─► [/meetings/:id/review]
                                                                  │ chấp nhận / sửa / bác
                                                                  ▼ Phát hành
                                              [/meetings/:id/minutes]  xem + tải .md/.json
                                              kho tri thức ─► [/qa]  hỏi đáp có trích dẫn
```

**4 đầu ra**

| Đầu ra | Nội dung |
|---|---|
| Transcript | `[00:47:12] Lan: Vậy mình chốt Postgres nhé` |
| Màn hình duyệt | Mục theo 7 loại; trạng thái, độ tin cậy, cờ cảnh báo; bấm vào mục là cuộn tới câu gốc; tab **Diễn biến chủ đề** cho thấy A bị thay thế bởi B lúc nào |
| Biên bản | Markdown + JSON (`MeetingItem[]`), chỉ gồm mục đã duyệt |
| Hỏi đáp | Câu trả lời kèm `[cuộc họp · hh:mm:ss · người nói]` |

---

## 3. Tech stack

| Lớp | Chọn | Lý do | Thay thế được |
|---|---|---|---|
| Ngôn ngữ backend | **Python 3.11+**, quản lý gói bằng **uv** | Hệ sinh thái AI/STT đều là Python; uv cài nhanh, có lockfile | Poetry |
| API | **FastAPI** + **Pydantic v2** | Async, tự sinh OpenAPI → frontend sinh type tự động; Pydantic dùng chung cho domain model và structured output của LLM | Litestar |
| ORM / migration | **SQLAlchemy 2.0 (async)** + **Alembic** (nằm trong `backend/`) | Chuẩn, có autogenerate migration | SQLModel |
| Cơ sở dữ liệu | **PostgreSQL 16 + pgvector** | Một kho cho cả dữ liệu có cấu trúc lẫn tìm kiếm ngữ nghĩa; truy vấn lai metadata + vector bằng một câu SQL | SQLite + Chroma (chỉ để demo) |
| Hàng đợi job | **Arq + Redis** | Async-native, nhẹ hơn Celery; STT và pipeline mất vài phút nên không chạy trong request HTTP | Celery, Dramatiq |
| Lưu file audio | Volume cục bộ (MVP) | Đơn giản; đổi sang S3 sau mà không sửa logic (qua interface `FileStore`) | MinIO / S3 |
| LLM | Wrapper riêng `ai/llm/` gọi **Claude hoặc GPT** qua API, bắt buộc structured output (JSON schema từ Pydantic) | Chất lượng tiếng Việt tốt; wrapper giúp đổi nhà cung cấp mà không sửa agent | Qwen/Llama nội bộ qua vLLM hoặc Ollama (endpoint tương thích OpenAI) |
| Điều phối agent | **LangGraph** (StateGraph) | Quản lý luồng đồ thị (graph-based), state có cấu trúc giữa các node agent, xử lý rẽ nhánh điều kiện (vd: retry/loopback khi validate trượt), hỗ trợ checkpointing và tích hợp sâu với Langfuse | Hàm async Python thuần, LlamaIndex Workflows |
| Chuyển giọng nói | **WhisperX** (faster-whisper) + **pyannote.audio 4.0** (model Community-1) | Có mốc thời gian theo từ + tách người nói; chạy nội bộ được | PhoWhisper (tinh chỉnh cho tiếng Việt), API trả phí (pyannoteAI Precision-2) |
| Embedding | **BAAI/bge-m3** hoặc **intfloat/multilingual-e5-base** qua sentence-transformers | Đa ngôn ngữ, hỗ trợ tiếng Việt, chạy nội bộ | Embedding API của nhà cung cấp LLM |
| So khớp trích dẫn | **rapidfuzz** | Kiểm tra trích dẫn có nguyên văn trong transcript, chịu được lỗi chính tả nhỏ | — |
| Frontend | **Next.js (App Router) + TypeScript** | Định tuyến theo thư mục, SSR khi cần | Vite + React |
| UI | **Tailwind CSS + shadcn/ui** | Có sẵn Dialog, Tabs, Badge cho màn hình duyệt | Mantine |
| Gọi API, trạng thái server | **TanStack Query** | Poll trạng thái job, cache, cập nhật lạc quan khi duyệt | SWR |
| Type giữa FE/BE | **openapi-typescript** sinh `types/api.ts` từ OpenAPI | Hai bên luôn khớp, không viết type tay | orval |
| Test | **pytest + pytest-asyncio**, **Vitest + Testing Library**, **Playwright** (e2e) | Chuẩn của từng phía | — |
| Theo dõi LLM | **Langfuse** (self-host, tuỳ chọn) + log có cấu trúc | Xem prompt, token, độ trễ từng lời gọi để debug và đánh giá | OpenTelemetry |
| Dev / CI | **Docker Compose**, ruff, mypy, ESLint, pre-commit, GitHub Actions | Một lệnh dựng đủ hạ tầng; CI chạy test + eval | — |

**Ghi chú phần cứng:** WhisperX + pyannote cần GPU để chạy nhanh. Máy không có GPU thì chạy worker STT trên Colab hoặc một máy có GPU, hoặc dùng API trả phí. P0 không phụ thuộc vào phần này.

---

## 4. Kiến trúc hệ thống

```
 Next.js (frontend)
     │  REST + poll trạng thái job
     ▼
 FastAPI (backend/app/api)
     │  endpoints → services → repositories
     │                    └──► ai/ (lõi AI, không import FastAPI)
     │
     ├──► PostgreSQL + pgvector   (meetings, utterances, acts, items, item_events, jobs, embeddings)
     ├──► Redis ◄── Arq worker    (transcribe, analyze, index)
     │                 └──► ai/pipeline ──► LLM API | WhisperX/pyannote
     └──► FileStore (volume)      (audio upload, transcript export)
```

**Quy tắc phụ thuộc:** `endpoints → services → repositories / ai`. Endpoint không gọi thẳng agent, `ai/` không biết gì về HTTP. Nhờ vậy cùng một lõi chạy được từ API, worker, CLI eval và bot Discord sau này.

---

## 5. Cấu trúc thư mục

```
meeting-intel/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/v1/endpoints/      # meetings, transcriptions, items, jobs, qa, health
│   │   ├── core/                  # config (pydantic-settings), logging
│   │   ├── db/                    # session, base
│   │   ├── models/                # ORM
│   │   ├── schemas/               # DTO request/response
│   │   ├── repositories/
│   │   ├── services/              # meeting, review, publish, export
│   │   ├── workers/               # arq: transcribe, analyze, index
│   │   └── ai/
│   │       ├── domain/            # models.py, enums.py, state_machine.py
│   │       ├── agents/            # normalize, extract, topics, validate, publish, qa
│   │       ├── pipeline.py        # LangGraph StateGraph điều phối agent
│   │       ├── llm/               # client.py, providers/{anthropic,openai,local}.py
│   │       ├── stt/               # whisperx.py
│   │       ├── retrieval/         # embedder.py, search.py
│   │       └── prompts/           # extract/v1.md, topics/v1.md, arbitrate/v1.md, qa/v1.md
│   ├── alembic/
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/                   # page routes (mục 11)
│   │   ├── features/              # transcribe, meetings, review, minutes, qa
│   │   ├── components/ui/         # shadcn
│   │   ├── lib/                   # api-client.ts, format.ts
│   │   └── types/api.ts           # sinh tự động
│   ├── package.json
│   └── Dockerfile
├── tests/
│   ├── backend/{unit,integration,api}/
│   ├── frontend/
│   ├── e2e/
│   └── fixtures/                  # transcript ngắn, audio 30s, golden nhỏ
├── evals/
│   ├── datasets/{transcripts,synthetic}/
│   ├── golden/
│   ├── metrics/
│   ├── runners/
│   ├── config.yaml
│   └── reports/                   # gitignore
├── docker-compose.yml
├── Makefile
├── .env.example
└── README.md
```

---

## 6. Data model

### 6.1 Domain model (`backend/app/ai/domain/models.py`)

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
    organizer: str | None = None          # người duyệt mặc định khi không có chủ trì
    participants: list[Participant] = []
    glossary: list[str] = []

class Utterance(BaseModel):
    id: str                               # "u0042"
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
    utterance_id: str
    speaker: str
    start: float
    act: Act
    quote: str                            # NGUYÊN VĂN
    topic_hint: str | None = None
    option: str | None = None
    content: str | None = None
    assignee: str | None = None
    due_text: str | None = None
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

### 6.2 Bảng PostgreSQL

| Bảng | Cột chính | Ghi chú |
|---|---|---|
| `meetings` | id, title, meeting_date, project, organizer, context (jsonb), status (`draft` / `analyzing` / `in_review` / `published`), published_at | |
| `utterances` | id, meeting_id, speaker, start, end, text | index (meeting_id, start) |
| `dialogue_acts` | id, meeting_id, utterance_id, act, option, topic_id, payload (jsonb) | lưu lại để xem "Diễn biến chủ đề" và debug |
| `topics` | id, meeting_id, question, history (jsonb) | lịch sử trạng thái từng phương án |
| `items` | id, meeting_id, type, status, review_state, data (jsonb), embedding vector(1024) | index HNSW trên embedding |
| `item_events` | id, item_id, actor, action (`created` / `approved` / `edited` / `rejected` / `reported` / `reopened`), before, after, reason, created_at | lịch sử ai sửa gì (mục 9.3) |
| `transcript_chunks` | id, meeting_id, start_ts, speakers, text, embedding | cửa sổ 6 câu, phục vụ hỏi đáp "vì sao" |
| `jobs` | id, kind (`transcribe` / `analyze` / `index`), meeting_id, status, step, progress, error, result (jsonb) | frontend poll bảng này |

Kích thước `vector(...)` lấy theo model embedding (bge-m3: 1024; multilingual-e5-base: 768).

---

## 7. Pipeline & đặc tả agent

```
(audio) Agent 0 STT ─┐
                     ▼
Agent 1 normalize ─► Agent 2 extract ─► Agent 3 topics + state machine ─► Agent 4 validate
                                                                              │
                         ┌────────────────────────────────────────────────────┘
                         ▼
          lưu items (review_state = pending) ─► NGƯỜI DUYỆT ─► Agent 5 publish ─► index ─► Agent 6 QA
```

| Agent | Input → Output | Cách làm | LLM? |
|---|---|---|---|
| 0 · STT | audio → `Utterance[]` (SPEAKER_xx) | WhisperX `language="vi"`, `initial_prompt` = glossary; pyannote diarization, có tham số min/max speakers; xuất `.txt` / `.srt` | Không |
| 1 · Normalize | file → `Utterance[]` đã chuẩn hoá + các đoạn | Parse `.txt` (`[hh:mm:ss] Tên: ...`), `.srt`, `.vtt`, `.docx`; map SPEAKER_xx → tên (LLM, giữ nhãn gốc nếu độ tin cậy < 0.6); sửa thuật ngữ theo glossary (rapidfuzz ≥ 90); chia đoạn 40 câu, chồng lấn 5 câu | Một phần |
| 2 · Extract | đoạn → `DialogueAct[]` | Structured output, chạy song song các đoạn; bỏ act trùng ở vùng chồng lấn | Có |
| 3 · Topics + state | `DialogueAct[]` → `Topic[]` → `MeetingItem[]` | 3a: LLM gom chủ đề + gộp tên gọi khác nhau của cùng phương án; 3b: máy trạng thái (code thuần, mục 8); 3c: sinh mục; 3d: LLM phân xử khi có dấu hiệu mâu thuẫn | 3a, 3d |
| 4 · Validate | `MeetingItem[]` → mục + flags | Kiểm tra trích dẫn nguyên văn, trường bắt buộc, mục trùng, độ tin cậy; đoạn có > 30% trích dẫn sai thì chạy lại Agent 2 một lần | Không |
| 5 · Publish | mục đã duyệt → `.md`, `.json`, embedding | Chỉ lấy mục `approved` / `edited`; đổi trạng thái meeting thành `published` | Không |
| 6 · QA | câu hỏi → câu trả lời + trích dẫn | Tách bộ lọc (dự án, ngày, người, loại mục) → truy vấn lai pgvector + metadata → đi theo chuỗi `superseded_by` tới mục mới nhất → LLM chỉ trả lời từ ngữ cảnh, không đủ thì nói không biết | Có |

**Quy tắc sinh mục (3c)**

| Nguồn | Mục tạo ra |
|---|---|
| Phương án ở trạng thái `DECIDED` | `decision` (FINAL), `supersedes` = các phương án bị thay thế, `rationale` lấy từ SUPPORT/OBJECT |
| Chủ đề không có phương án nào được chốt | `open_question` |
| `DEFER` | `open_question` + `action_item` "xin ý kiến…" nếu có người nhận |
| `DECIDE` có điều kiện | `decision` + `open_question` theo dõi điều kiện |
| Nhóm act giao việc | `action_item`; người phụ trách và hạn lấy theo act mới nhất |
| `RAISE_BLOCKER` / `REQUEST` / `FEEDBACK` / `KNOWLEDGE` | `blocker` / `request` / `feedback` / `knowledge` |
| `ASK` không có câu trả lời | `open_question` |
| `HYPOTHETICAL` | bỏ |

Prompt lưu theo phiên bản trong `ai/prompts/<agent>/vN.md`; phiên bản đang dùng đặt trong config để eval so sánh được giữa các phiên bản.

---

## 8. Máy trạng thái (`ai/domain/state_machine.py`)

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

DISCUSS = {Act.SUPPORT, Act.OBJECT, Act.AMEND}

def run_topic(topic: Topic, acts: list[DialogueAct]) -> Topic:
    for a in sorted(acts, key=lambda x: x.start):
        if a.option is None:
            if a.act == Act.DEFER:
                topic.deferred = True
            continue
        opt = topic.options.setdefault(a.option, Option(label=a.option))
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
            opt.state = OptState.REJECTED
        elif a.act == Act.REOPEN and opt.state == OptState.DECIDED:
            opt.state, opt.decided_act = OptState.DISCUSSED, None
            for o in topic.options.values():
                if o.superseded_by == opt.label:
                    o.state, o.superseded_by = OptState.DISCUSSED, None
        elif a.act == Act.DEFER:
            topic.deferred = True

        opt.history.append((a.start, a.act.value, opt.state.value if opt.state else "-"))

    if not any(o.state == OptState.DECIDED for o in topic.options.values()):
        for o in topic.options.values():
            if o.state in (None, OptState.PROPOSED, OptState.DISCUSSED):
                o.state = OptState.OPEN
    return topic
```

**Unit test bắt buộc** (`tests/backend/unit/test_state_machine.py`)

| Kịch bản | Chuỗi act | Kỳ vọng |
|---|---|---|
| A→B cơ bản | PROPOSE A, OBJECT A, PROPOSE B, SUPPORT B, DECIDE B | B = DECIDED, A = SUPERSEDED (bởi B) |
| Chốt A rồi đổi B | PROPOSE A, DECIDE A, PROPOSE B, DECIDE B | B = DECIDED, A = SUPERSEDED |
| Quay lại A | DECIDE A, DECIDE B, DECIDE A | A = DECIDED, B = SUPERSEDED |
| Mở lại, không chốt | PROPOSE A, DECIDE B, REOPEN B | A, B = OPEN |
| Không ai chốt | PROPOSE A, SUPPORT A | A = OPEN → `open_question` |
| Bác | PROPOSE A, REJECT A, PROPOSE B, DECIDE B | A = REJECTED, B = DECIDED |
| Hoãn | PROPOSE A, DEFER (không có option) | deferred, A = OPEN |

---

## 9. Quy tắc nghiệp vụ

### 9.1 Quyết định thật và ý kiến của người có chức vụ cao
- Chức vụ **không** biến ý kiến thành quyết định. Chỉ act `DECIDE` (có tín hiệu chốt rõ) mới tạo quyết định.
- Các câu "hay là…", "em nghĩ…", "chắc là…", "để xem…" không phải `DECIDE`.
- Độ tin cậy của quyết định:

```python
def decision_confidence(opt, ctx) -> float:
    a = opt.decided_act
    c = a.confidence
    makers = {p.name for p in ctx.participants if p.is_decision_maker}
    if makers and a.speaker not in makers:
        c *= 0.8                                   # người chốt không có thẩm quyền
    if any(x.act == Act.OBJECT and x.start > a.start for x in opt.acts):
        c *= 0.6                                   # có phản đối sau khi chốt
    return round(c, 2)
```

- Gọi LLM phân xử (3d) khi có một trong các dấu hiệu: hai `DECIDE` khác phương án cách nhau < 60 giây; `DECIDE` từ người không có thẩm quyền rồi có `OBJECT` ngay sau; có `OBJECT` sau `DECIDE` mà không có `REOPEN`. Nếu vẫn mơ hồ: để `open_question` + cờ `needs_confirmation`.

### 9.2 Ai duyệt biên bản
- Thứ tự ưu tiên: người chủ trì (participant được đánh dấu) → `organizer` (người tạo lịch họp) → người upload.
- Biên bản **không bao giờ tự phát hành**. Chưa duyệt thì meeting ở trạng thái `in_review`; P2 sẽ nhắc qua kênh chat.

### 9.3 Người duyệt sửa sai
- Bằng chứng gốc luôn đi kèm mục; mọi thay đổi ghi vào `item_events`.
- Khi một bản sửa đổi `status` hoặc `content` của một `decision` sang phương án **khác** phương án trong bằng chứng, giao diện bắt buộc ghi `reason`.
- Sau khi phát hành, người tham dự bấm "Báo sai" → tạo event `reported`. Chủ trì xem lại và có thể mở lại mục.
- Bản sửa chỉ được dùng làm ví dụ few-shot hoặc dữ liệu eval sau khi chủ trì xác nhận.

### 9.4 Tri thức hay chuyện phiếm
- Phép thử trong prompt: *"Một người mới vào dự án 3 tháng sau có cần biết điều này không?"*
- Là tri thức: quy ước, ràng buộc kỹ thuật/kinh doanh, lý do của quyết định, bài học từ sự cố, sự thật về khách hàng hoặc hệ thống.
- Không phải tri thức: cảm xúc, chuyện ngoài lề, trạng thái tạm thời (chẳng hạn "staging đang hỏng" là `blocker`).
- Khi phân vân thì **không** tạo mục `knowledge`; người duyệt có thể tự thêm.

### 9.5 Kiểm tra trường bắt buộc (Agent 4)

| Loại | Bắt buộc | Thiếu thì |
|---|---|---|
| decision | owner (người chốt), ≥ 1 evidence | `missing_owner` |
| action_item | owner, due_date | `missing_owner`, `missing_due_date` |
| request | requester | `missing_requester` |
| mọi loại | trích dẫn khớp nguyên văn (`partial_ratio ≥ 90`) | bỏ evidence sai; mục không còn evidence thì bỏ mục |
| mọi loại | confidence ≥ 0.8 | `low_confidence`, đưa lên đầu màn hình duyệt |

---

## 10. API (`/api/v1`)

| Method | Endpoint | Việc |
|---|---|---|
| POST | `/transcriptions` | upload audio → `{job_id}` |
| GET | `/transcriptions/{id}/download?format=txt\|srt` | tải transcript |
| POST | `/meetings` | multipart: file transcript/audio + `context` (JSON) → `{meeting_id, job_id}` |
| GET | `/jobs/{id}` | `{status, step, progress, error}` |
| GET | `/meetings` | danh sách, lọc theo dự án/trạng thái |
| GET | `/meetings/{id}` | ngữ cảnh + transcript |
| GET | `/meetings/{id}/items` | mục cần duyệt (sắp xếp: có cờ lên trước) |
| GET | `/meetings/{id}/topics` | diễn biến chủ đề (history từng phương án) |
| PATCH | `/items/{id}` | `{action: approve\|edit\|reject, patch?, reason?}` |
| POST | `/meetings/{id}/items/approve-clean` | chấp nhận hàng loạt mục không có cờ |
| POST | `/meetings/{id}/publish` | phát hành + tạo job index |
| GET | `/meetings/{id}/export?format=md\|json` | tải biên bản |
| POST | `/items/{id}/report` | báo sai sau phát hành |
| POST | `/qa` | `{question, project?}` → `{answer, citations[]}` |

---

## 11. Frontend

| Route | Thành phần chính |
|---|---|
| `/` | danh sách cuộc họp + trạng thái |
| `/transcribe` | upload audio, chọn số người nói, tiến trình job, bảng transcript, nút tải `.txt` / `.srt` |
| `/meetings/new` | upload file; form ngữ cảnh (tiêu đề, ngày, dự án, người tham gia + vai trò + "người ra quyết định", glossary); tiến trình theo từng bước |
| `/meetings/[id]/review` | **Hai cột:** trái là tabs 7 loại mục (`ItemCard`: nội dung sửa được, owner, due, badge trạng thái/độ tin cậy/cờ, phương án bị thay thế gạch ngang); phải là `TranscriptPanel` tự cuộn tới câu gốc. Tab **Diễn biến chủ đề** (`TopicTimeline`): đường thời gian từng phương án. Nút "Chấp nhận mục sạch", "Phát hành" |
| `/meetings/[id]/minutes` | biên bản render từ Markdown, nút tải `.md` / `.json`, nút "Báo sai" trên từng mục |
| `/qa` | khung chat, gợi ý câu hỏi mẫu, `CitationChip` mở đoạn transcript |

`TopicTimeline` là màn hình đáng đầu tư nhất khi demo, vì nó cho thấy trực quan A bị thay thế bởi B lúc nào.

---

## 12. Đánh giá (`evals/`)

| Chỉ số | Cách đo | Ngưỡng MVP |
|---|---|---|
| Độ chính xác quyết định cuối | % chủ đề mà mục FINAL khớp nhãn | ≥ 0.90 |
| Precision / recall theo loại mục | so khớp mục với golden (nội dung tương đồng + cùng loại) | P ≥ 0.85, R ≥ 0.75 |
| Đúng người phụ trách + hạn chót | % action_item đúng cả hai trường | ≥ 0.85 |
| Bám bằng chứng | % evidence khớp nguyên văn | 1.00 |
| Kịch bản bẫy | % kịch bản synthetic cho đúng trạng thái cuối | 1.00 |

- **Dataset:** 15–20 transcript tiếng Việt gán nhãn + bộ synthetic (A→B, B→A, quay lại A, chốt có điều kiện, chờ cấp trên, đùa/giả định, giao việc ngầm, hạn chót tương đối).
- **Chạy:** `PYTHONPATH=backend python -m evals.runners.run_pipeline --prompt-version v1`
- **CI:** chạy eval khi PR đụng tới `ai/prompts/` hoặc `ai/agents/`; fail nếu dưới ngưỡng.
- **Phân biệt với `tests/`:** tests dùng LLM giả lập và cho kết quả đạt/không đạt; evals gọi LLM thật và cho điểm số.

---

## 13. Setup

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
    volumes: [files:/data/files]
  worker:
    build: ./backend
    command: arq app.workers.main.WorkerSettings
    env_file: .env
    depends_on: [db, redis]
    volumes: [files:/data/files]
  frontend:
    build: ./frontend
    environment: { NEXT_PUBLIC_API_URL: http://localhost:8000 }
    ports: ["3000:3000"]
volumes: { pgdata: {}, files: {} }
```

**`.env.example`**

```
DATABASE_URL=postgresql+asyncpg://app:app@db:5432/meeting
REDIS_URL=redis://redis:6379
FILE_STORE_DIR=/data/files
LLM_PROVIDER=anthropic          # anthropic | openai | openai_compatible
LLM_MODEL=
LLM_BASE_URL=                   # cho vLLM/Ollama
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024
HF_TOKEN=                       # pyannote: cần chấp nhận điều khoản model trên Hugging Face
WHISPER_MODEL=large-v3
DEVICE=cuda                     # cpu nếu không có GPU
PROMPT_VERSION=v1
LANGFUSE_HOST=
```

**`Makefile`**

```
up:       docker compose up --build
migrate:  cd backend && alembic upgrade head
test:     pytest tests/backend && cd frontend && npm run test
e2e:      npx playwright test tests/e2e
eval:     PYTHONPATH=backend python -m evals.runners.run_pipeline
types:    cd frontend && npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts
```

**Cấu hình test** (vì `tests/` nằm ngoài): trong `backend/pyproject.toml` đặt `testpaths = ["../tests/backend"]`, `pythonpath = ["."]`; trong `frontend/vitest.config.ts` đặt `include: ["../tests/frontend/**/*.test.{ts,tsx}"]`.

---

## 14. Kế hoạch

**P0 — 3 ngày**

| Ngày | Việc | Xong khi |
|---|---|---|
| 1 | Repo + docker compose; domain model; state machine + 7 unit test; parser transcript; viết bộ kịch bản bẫy và 3 transcript mẫu kèm golden | `pytest` xanh; `make up` chạy |
| 2 | LLM wrapper; Agent 2 extract; Agent 3 topics + sinh mục; Agent 4 validate; worker job `analyze`; API meetings/items/jobs | chạy `payment_v2.txt` đạt ≥ 8/10 mục khớp golden |
| 3 | Màn hình duyệt + TopicTimeline; publish + export `.md`/`.json`; runner eval | demo luồng end-to-end; báo cáo eval đầu tiên |

**P1 — khoảng 1 tuần:** Agent 6 QA (pgvector + chuỗi thay thế) và trang `/qa`; Agent 0 STT + trang `/transcribe`; mở rộng dataset eval lên 15–20 transcript.

**P2 — sau khi P0 đạt ngưỡng ở nhóm thí điểm:**
- tích hợp Jira/Notion/Slack;
- bot Discord (ghi âm kênh thoại, `/hoi`);
- agenda tự động cho họp sau;
- nối quyết định xuyên cuộc họp;
- phát hiện mâu thuẫn với quyết định cũ.

---

## 15. Dữ liệu mẫu (`evals/datasets/transcripts/payment_v2.txt`)

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

**Golden** (ngày họp 08/10/2026; Lan là người ra quyết định), lưu thành `evals/golden/payment_v2.json`:

| Loại | Nội dung | Ghi chú |
|---|---|---|
| decision | Dùng PostgreSQL cho dịch vụ thanh toán | FINAL, owner Lan, supersedes MongoDB, evidence 00:03:30 |
| action_item | Dựng schema Postgres | Minh, due 16/10/2026 ("thứ Sáu tuần sau") |
| action_item | Sửa môi trường staging | Minh tự nhận, cờ `missing_due_date` |
| action_item | Xin ý kiến anh Tuấn về replica đọc | Lan |
| action_item | Xuất báo cáo giao dịch lỗi hằng tuần | Hoa, bắt đầu tuần sau |
| blocker | Staging hỏng, chưa test được API cũ | Hoa nêu |
| request | CS cần báo cáo giao dịch lỗi hằng tuần | requester: CS |
| open_question | Có cần replica đọc không? | chờ anh Tuấn |
| knowledge | Dịch vụ thanh toán bắt buộc giao dịch ACID | |
| feedback | Tài liệu API đợt này viết rõ hơn | tích cực |
| — | "Giả sử bỏ phần hoàn tiền…" | HYPOTHETICAL, không tạo mục |