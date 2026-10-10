# Kế hoạch 1/5 — Lõi AI (M2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây gói Python `app.ai` thuần (không HTTP, không DB, không Clerk): transcript → `MeetingItem[]` với đúng trạng thái cuối, cùng runner eval đo theo ngưỡng của spec.

**Architecture:** Hàm thuần cho mọi bước tất định (parser, chuẩn hoá, máy trạng thái, hạn chót, sinh mục, validate); agent LLM gọi qua giao diện `LLMClient` (thật: Anthropic `messages.parse` với schema Pydantic; test: `FakeLLM`). LangGraph `StateGraph` nối các bước, có vòng chạy lại cho đoạn trích dẫn sai. Kế hoạch này làm trước M1 vì lõi không phụ thuộc hạ tầng và là phần quyết định đúng/sai của cả sản phẩm.

**Tech Stack:** Python 3.11+, uv, Pydantic v2, anthropic SDK, LangGraph, rapidfuzz, python-docx, pytest + pytest-asyncio, ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-10-10-meetmind-mvp-design.md` (đọc mục 7–10, 13.2, 16).

**Các kế hoạch tiếp theo** (viết sau khi kế hoạch này xong): 2 · Nền backend + Clerk + API (M1-BE, M3-BE) · 3 · Frontend (M1-FE, M3-FE) · 4 · Hỏi đáp (M4) · 5 · Hoàn thiện (M5).

## Global Constraints

- Python `>=3.11`; quản lý gói bằng `uv`; mã nguồn trong `backend/app/`, test trong `tests/backend/`, eval trong `evals/` (spec mục 6).
- `backend/pyproject.toml`: `testpaths = ["../tests/backend"]`, `pythonpath = ["."]`, `asyncio_mode = "auto"`.
- `app/ai/` không import FastAPI, SQLAlchemy, Redis hay bất cứ gì của `app.api`/`app.db`.
- `tests/` không bao giờ gọi API thật; mọi LLM trong test là `FakeLLM`.
- Ngưỡng: so khớp trích dẫn `partial_ratio ≥ 90`; glossary `≥ 90`; chunk 40 câu, chồng lấn 5; chạy lại extract khi > 30% act sai, tối đa 1 lần; `low_confidence` khi < 0.6; phạt ×0.85 (người chốt không có thẩm quyền), ×0.6 (phản đối sau khi chốt); arbitrate khi hai DECIDE khác phương án cách nhau < 60 giây.
- Model mặc định: `claude-sonnet-5-5` (extract, topics), `claude-opus-5-5` (arbitrate); cấu hình được.
- Prompt ở `backend/app/ai/prompts/<agent>/v1.md`, viết bằng tiếng Việt.
- Tuần bắt đầu thứ Hai; mốc thời gian hiển thị `hh:mm:ss`.
- Commit nhỏ sau mỗi task, message tiếng Anh dạng `feat:`/`test:`/`chore:`, kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Transcript "bẩn":** có BOM UTF-8, xuống dòng CRLF, dòng trống, dòng không có mốc thời gian (câu nói bị xuống dòng). Kỳ vọng: BOM/CRLF bỏ qua, dòng không có mốc được nối vào câu trước — test ở Task 3.
2. **Tên người nói lệch chữ hoa/khoảng trắng** so với danh sách người tham gia (`"lan "` vs `"Lan"`). Kỳ vọng: so khớp người ra quyết định không phân biệt hoa thường và khoảng trắng — test ở Task 10.
3. **LLM trả dữ liệu tham chiếu không tồn tại** (`utterance_id` lạ, `act_id` lạ, option không có trong bảng gộp). Kỳ vọng: bỏ phần lạ, không crash — test ở Task 7 và Task 8.
4. **Cuộc họp không có quyết định nào / transcript rỗng sau khi parse.** Kỳ vọng: transcript rỗng → `TranscriptParseError`; không có quyết định → pipeline trả danh sách mục (có thể rỗng), không lỗi — test ở Task 3 và Task 12.
5. **Transcript dài (~400 câu).** Kỳ vọng: số lời gọi extract song song không vượt `max_concurrency` (mặc định 4) — test ở Task 12.

---

## File Structure

```
backend/
  pyproject.toml                       # Task 1
  app/__init__.py
  app/ai/__init__.py
  app/ai/config.py                     # AISettings (Task 6)
  app/ai/errors.py                     # TranscriptParseError, LLMError, LLMRefusal, AnalysisError (Task 1)
  app/ai/domain/enums.py               # Act, ItemType, ItemStatus, ReviewState, OptState (Task 2)
  app/ai/domain/models.py              # Participant, MeetingContext, Utterance, DialogueAct, Evidence, MeetingItem (Task 2)
  app/ai/domain/timefmt.py             # fmt_ts, parse_ts (Task 2)
  app/ai/domain/state_machine.py       # Option, Topic, run_topic (Task 4)
  app/ai/domain/due_dates.py           # resolve_due (Task 5)
  app/ai/parsing/__init__.py           # parse_transcript (Task 3)
  app/ai/parsing/{txt,srt,vtt,docx}.py
  app/ai/agents/normalize.py           # apply_glossary, make_chunks, Chunk (Task 3)
  app/ai/llm/client.py                 # LLMClient protocol, AnthropicLLM (Task 6)
  app/ai/llm/fake.py                   # FakeLLM (Task 6)
  app/ai/llm/prompts.py                # load_prompt (Task 6)
  app/ai/agents/extract.py             # extract_chunk, dedupe_acts (Task 7)
  app/ai/agents/check_quotes.py        # check_quotes (Task 7)
  app/ai/agents/topics.py              # assign_topics (Task 8)
  app/ai/agents/arbitrate.py           # arbitration_reasons, arbitrate (Task 9)
  app/ai/agents/build_items.py         # decision_confidence, build_items (Task 10)
  app/ai/agents/validate.py            # validate_items (Task 11)
  app/ai/pipeline.py                   # analyze_transcript, AnalysisResult (Task 12)
  app/ai/prompts/{extract,topics,arbitrate}/v1.md
tests/backend/unit/…                   # một file test cho mỗi module
tests/backend/integration/test_pipeline_fake.py
tests/fixtures/transcripts/…, tests/fixtures/llm/payment_v2/*.json
evals/
  __init__.py, config.yaml
  datasets/transcripts/*.txt, datasets/synthetic/*.txt
  golden/*.json
  metrics/matching.py, metrics/scores.py
  runners/run_pipeline.py
```

---

### Task 1: Khung gói backend

**Files:**
- Create: `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/ai/__init__.py`, `backend/app/ai/errors.py`, `.gitignore`
- Test: `tests/backend/unit/test_smoke.py`

**Interfaces:**
- Produces: `app.ai.errors` với `class MeetMindError(Exception)`, `TranscriptParseError(MeetMindError)`, `LLMError(MeetMindError)`, `LLMRefusal(LLMError)`, `AnalysisError(MeetMindError)` (thuộc tính `step: str`).

- [ ] **Step 1:** Kiểm tra `uv --version` chạy được (nếu không: `pip install uv`).
- [ ] **Step 2:** Tạo `backend/pyproject.toml`: project `meetmind-backend`, `requires-python = ">=3.11"`; dependencies `pydantic>=2.7`, `anthropic`, `langgraph`, `rapidfuzz`, `python-docx`, `pyyaml`; dev group `pytest`, `pytest-asyncio`, `ruff`, `mypy`. `[tool.pytest.ini_options]` theo Global Constraints. `[tool.ruff] line-length = 100`. Chạy `cd backend && uv sync`.
- [ ] **Step 3:** `.gitignore` gồm `.venv/`, `__pycache__/`, `.env`, `evals/reports/`, `.claude/settings.local.json`, `node_modules/`.
- [ ] **Step 4:** Viết test:

```python
from app.ai.errors import AnalysisError, LLMRefusal, LLMError

def test_error_hierarchy():
    assert issubclass(LLMRefusal, LLMError)
    e = AnalysisError("boom", step="extract")
    assert e.step == "extract" and "boom" in str(e)
```

- [ ] **Step 5:** `cd backend && uv run pytest ../tests/backend/unit/test_smoke.py -v` → FAIL (chưa có module). Viết `errors.py`. Chạy lại → PASS. `uv run ruff check . && uv run mypy app` sạch.
- [ ] **Step 6:** Commit `chore: scaffold backend package`.

---

### Task 2: Domain model, enum, định dạng thời gian

**Files:**
- Create: `backend/app/ai/domain/__init__.py`, `enums.py`, `models.py`, `timefmt.py`
- Test: `tests/backend/unit/test_domain_models.py`, `tests/backend/unit/test_timefmt.py`

**Interfaces:**
- Produces: các class đúng như spec mục 7.1 (`Utterance` có `seq: int`; `DialogueAct` có `seq`, `topic_id`); `OptState` đặt trong `enums.py`. `fmt_ts(seconds: float) -> str` ("00:47:12", làm tròn xuống giây); `parse_ts(s: str) -> float` nhận `hh:mm:ss`, `mm:ss`, `hh:mm:ss,mmm`, `hh:mm:ss.mmm`, lỗi → `ValueError`.

- [ ] **Step 1: Test**

```python
def test_fmt_and_parse_ts():
    assert fmt_ts(2832.9) == "00:47:12"
    assert parse_ts("00:47:12") == 2832
    assert parse_ts("47:12") == 2832
    assert parse_ts("00:00:01,500") == 1.5
    with pytest.raises(ValueError): parse_ts("abc")

def test_dialogue_act_confidence_bounds():
    with pytest.raises(ValidationError):
        DialogueAct(id="a1", utterance_id="u0001", seq=1, speaker="Lan", start=0,
                    act=Act.DECIDE, quote="x", confidence=1.2)

def test_meeting_item_defaults():
    it = MeetingItem(id="i1", meeting_id="m1", type=ItemType.DECISION, content="c", evidence=[])
    assert it.status == ItemStatus.FINAL and it.review_state == ReviewState.PENDING and it.flags == []
```

- [ ] **Step 2:** Chạy → FAIL. **Step 3:** Viết các module. **Step 4:** Chạy → PASS.
- [ ] **Step 5:** Commit `feat: add domain models and time helpers`.

---

### Task 3: Parser transcript + chuẩn hoá (Agent 1)

**Files:**
- Create: `backend/app/ai/parsing/__init__.py`, `txt.py`, `srt.py`, `vtt.py`, `docx.py`, `backend/app/ai/agents/__init__.py`, `backend/app/ai/agents/normalize.py`
- Create fixtures: `tests/fixtures/transcripts/{basic.txt, dirty.txt, basic.srt, basic.vtt, basic.docx}` (docx sinh bằng python-docx trong `conftest.py` để khỏi commit file nhị phân)
- Test: `tests/backend/unit/test_parsing.py`, `tests/backend/unit/test_normalize.py`

**Interfaces:**
- Produces: `parse_transcript(filename: str, data: bytes) -> list[Utterance]` (chọn parser theo đuôi; id `u0000`, `u0001`… theo `seq`; `end` lấy từ srt/vtt, với txt là `start` câu kế tiếp hoặc `None`). Đuôi lạ, không đọc được UTF-8, hoặc ra 0 câu → `TranscriptParseError`.
- Produces: `apply_glossary(utts: list[Utterance], glossary: list[str]) -> list[Utterance]` (thay từ/cụm từ trong câu có `fuzz.ratio ≥ 90` và không khớp chính xác với thuật ngữ; so khớp cửa sổ cùng số từ với thuật ngữ, không phân biệt hoa thường).
- Produces: `class Chunk(BaseModel): index: int; utterances: list[Utterance]`; `make_chunks(utts, size=40, overlap=5) -> list[Chunk]`.
- Định dạng `.txt`: `[hh:mm:ss] Tên: nội dung`. `.srt`/`.vtt`: tên người nói lấy từ tiền tố `Tên:` trong phần text, hoặc thẻ `<v Tên>` của vtt; không có thì `"Unknown"`. `.docx`: mỗi đoạn văn được coi như một dòng `.txt`.

- [ ] **Step 1: Test**

```python
def test_txt_basic():
    u = parse_transcript("a.txt", b"[00:00:05] Lan: Xin chao\n[00:00:20] Minh: Chao chi\n")
    assert [x.id for x in u] == ["u0000", "u0001"]
    assert (u[0].speaker, u[0].start, u[0].end, u[0].text) == ("Lan", 5, 20, "Xin chao")

def test_txt_dirty_bom_crlf_continuation():
    data = "﻿[00:00:05] Lan: Dong mot\r\n\r\ntiep tuc dong mot\r\n[00:00:09] Hoa: Hai\r\n".encode()
    u = parse_transcript("a.txt", data)
    assert len(u) == 2 and u[0].text == "Dong mot tiep tuc dong mot"

def test_srt_and_vtt_speaker():
    assert parse_transcript("a.srt", SRT)[0].speaker == "Lan"
    assert parse_transcript("a.vtt", VTT)[0].speaker == "Minh"   # <v Minh>

def test_docx(docx_bytes):
    assert parse_transcript("a.docx", docx_bytes)[0].speaker == "Lan"

@pytest.mark.parametrize("name,data", [("a.pdf", b"x"), ("a.txt", b""), ("a.txt", b"\xff\xfe\x00")])
def test_parse_errors(name, data):
    with pytest.raises(TranscriptParseError): parse_transcript(name, data)

def test_glossary_fixes_near_miss():
    u = apply_glossary([utt("Mình dùng Postgress nhé")], ["Postgres"])
    assert u[0].text == "Mình dùng Postgres nhé"

def test_chunks_overlap():
    ch = make_chunks([utt(str(i)) for i in range(85)], size=40, overlap=5)
    assert [len(c.utterances) for c in ch] == [40, 40, 15]
    assert ch[1].utterances[0].seq == 35
```

- [ ] **Step 2:** Chạy → FAIL. **Step 3:** Viết các module. **Step 4:** Chạy → PASS.
- [ ] **Step 5:** Commit `feat: add transcript parsers and normalization`.

---

### Task 4: Máy trạng thái

**Files:**
- Create: `backend/app/ai/domain/state_machine.py`
- Test: `tests/backend/unit/test_state_machine.py`

**Interfaces:**
- Produces: `Option`, `Topic`, `run_topic(topic: Topic, acts: list[DialogueAct]) -> Topic` — **code đúng như spec mục 9** (chép nguyên, kể cả `_restore_superseded_by`, `_resolve_option`, `INACTIVE`), thêm một trường `Topic.needs_confirmation: bool = False` (Task 9 đặt, Task 10 đọc).

- [ ] **Step 1: Test** — helper `act(kind, option, start, seq=None)` tạo `DialogueAct` tối thiểu (seq mặc định = start). Một test có tham số cho 12 kịch bản ở bảng spec mục 9; mỗi ca khai báo chuỗi `(Act, option|None, start, seq)` và kỳ vọng `{label: (OptState, superseded_by)}`, cộng `deferred` và `len(ambiguous_decides)` khi có. Ví dụ:

```python
CASES = {
  "a_to_b": ([(P,"A",1),(O,"A",2),(P,"B",3),(S,"B",4),(D,"B",5)],
             {"A": (SUPERSEDED,"B"), "B": (DECIDED,None)}),
  "reject_decided": ([(P,"A",1),(D,"B",2),(R,"B",3)],
             {"A": (OPEN,None), "B": (REJECTED,None)}),
  "same_ts": ([(D,"A",5,1),(D,"B",5,2)], {"A": (SUPERSEDED,"B"), "B": (DECIDED,None)}),
  # … đủ 12 ca theo bảng spec mục 9
}
```

Thêm assert riêng: ca 7 `topic.deferred is True`; ca 10 `len(topic.ambiguous_decides) == 1`; ca 1 `opt["B"].decided_act.start == 5`; mọi ca lịch sử `history` của mỗi option có số phần tử bằng số act gắn vào option đó.

- [ ] **Step 2:** Chạy → FAIL. **Step 3:** Viết module theo spec. **Step 4:** Chạy → 12/12 PASS.
- [ ] **Step 5:** Commit `feat: add topic state machine with 12 scenario tests`.

---

### Task 5: Hạn chót tương đối

**Files:**
- Create: `backend/app/ai/domain/due_dates.py`
- Test: `tests/backend/unit/test_due_dates.py`

**Interfaces:**
- Produces: `resolve_due(due_text: str | None, meeting_date: date) -> date | None` — các mẫu ở spec mục 10.6. Chuẩn hoá: casefold, bỏ dấu câu cuối, chấp nhận "thứ 2…thứ 7"/"thứ hai…thứ bảy", "chủ nhật"/"cn", tiền tố "trước", "hạn", "deadline", "trước khi hết". Có "bắt đầu" → `None`.

- [ ] **Step 1: Test** (họp thứ Năm 08/10/2026 = `D`):

```python
@pytest.mark.parametrize("text,expected", [
  ("thứ Sáu tuần sau", date(2026,10,16)), ("trước thứ 6 tuần sau", date(2026,10,16)),
  ("thứ Hai tuần này", date(2026,10,5)), ("thứ Sáu", date(2026,10,9)),
  ("thứ Năm", date(2026,10,15)),                       # cùng thứ với ngày họp → tuần sau
  ("ngày mai", date(2026,10,9)), ("ngày kia", date(2026,10,10)), ("ngày mốt", date(2026,10,10)),
  ("3 ngày nữa", date(2026,10,11)), ("hôm nay", D),
  ("cuối tuần", date(2026,10,9)), ("cuối tuần sau", date(2026,10,16)),
  ("cuối tháng", date(2026,10,31)), ("20/10", date(2026,10,20)), ("05/01", date(2027,1,5)),
  ("20/10/2026", date(2026,10,20)), ("ngày 25", date(2026,10,25)), ("ngày 3", date(2026,11,3)),
  ("bắt đầu từ tuần sau", None), ("sớm nhất có thể", None), (None, None),
])
def test_resolve_due(text, expected): assert resolve_due(text, D) == expected

def test_sunday_meeting_next_week():
    assert resolve_due("thứ Hai tuần sau", date(2026,10,11)) == date(2026,10,12)
```

- [ ] **Step 2:** Chạy → FAIL. **Step 3:** Viết module (regex + bảng thứ → `weekday()`). **Step 4:** Chạy → PASS.
- [ ] **Step 5:** Commit `feat: add Vietnamese relative due-date resolver`.

---

### Task 6: Wrapper LLM, FakeLLM, tải prompt, cấu hình

**Files:**
- Create: `backend/app/ai/config.py`, `backend/app/ai/llm/__init__.py`, `client.py`, `fake.py`, `prompts.py`
- Test: `tests/backend/unit/test_llm_client.py`

**Interfaces:**
- Produces:

```python
class AISettings(BaseModel):
    prompt_version: str = "v1"
    models: dict[str, str] = {"default": "claude-sonnet-5-5", "arbitrate": "claude-opus-5-5"}
    max_tokens: int = 16000
    max_concurrency: int = 4
    def model_for(self, agent: str) -> str: ...      # models.get(agent, models["default"])

class LLMClient(Protocol):
    async def structured(self, *, agent: str, system: str, user: str, schema: type[T]) -> T: ...

class AnthropicLLM:            # implements LLMClient
    def __init__(self, settings: AISettings, client: anthropic.AsyncAnthropic | None = None): ...

class FakeLLM:                 # implements LLMClient
    def __init__(self, responses: dict[str, list[BaseModel | dict | Callable[[str], BaseModel | dict]]]): ...
    calls: list[tuple[str, str]]          # (agent, user)
    max_in_flight: int                    # số lời gọi đồng thời lớn nhất đã thấy

def load_prompt(agent: str, version: str) -> str   # đọc app/ai/prompts/<agent>/<version>.md
```

- `AnthropicLLM.structured` gọi `await client.messages.parse(model=settings.model_for(agent), max_tokens=settings.max_tokens, system=system, messages=[{"role": "user", "content": user}], output_format=schema, extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"}, extra_body={"fallbacks": "default"})`; trả `response.parsed_output`. `stop_reason == "refusal"` → `LLMRefusal`; `parsed_output is None` hoặc `anthropic.APIError` → `LLMError` (giữ `__cause__`). Client mặc định `AsyncAnthropic(max_retries=4)` (SDK tự retry 408/409/429/5xx).
- `FakeLLM.structured` lấy phần tử kế tiếp trong danh sách của `agent` (callable thì gọi với `user`), validate thành `schema`; hết phần tử → `AssertionError` nêu tên agent; `await asyncio.sleep(0)` để đo `max_in_flight`.

- [ ] **Step 1: Test**

```python
async def test_fake_llm_returns_validated_and_records():
    llm = FakeLLM({"extract": [{"acts": []}]})
    out = await llm.structured(agent="extract", system="s", user="u", schema=ExtractOut)
    assert out.acts == [] and llm.calls == [("extract", "u")]

async def test_fake_llm_exhausted():
    with pytest.raises(AssertionError, match="extract"):
        await FakeLLM({"extract": []}).structured(agent="extract", system="", user="", schema=ExtractOut)

async def test_anthropic_llm_passes_model_and_schema():
    stub = StubAsyncAnthropic(parsed=ExtractOut(acts=[]), stop_reason="end_turn")
    llm = AnthropicLLM(AISettings(), client=stub)
    await llm.structured(agent="arbitrate", system="s", user="u", schema=ExtractOut)
    assert stub.kwargs["model"] == "claude-opus-5-5" and stub.kwargs["output_format"] is ExtractOut

async def test_anthropic_llm_refusal():
    stub = StubAsyncAnthropic(parsed=None, stop_reason="refusal")
    with pytest.raises(LLMRefusal):
        await AnthropicLLM(AISettings(), client=stub).structured(agent="extract", system="", user="", schema=ExtractOut)

def test_load_prompt_missing_version():
    with pytest.raises(FileNotFoundError): load_prompt("extract", "v999")
```

(`StubAsyncAnthropic` trong test: object có `messages.parse` async ghi lại `kwargs` và trả object có `parsed_output`, `stop_reason`. `ExtractOut` là model nhỏ khai báo trong test.)

- [ ] **Step 2:** Chạy → FAIL. **Step 3:** Viết module; tạo file rỗng `app/ai/prompts/extract/v1.md` để `load_prompt` có đích. **Step 4:** Chạy → PASS.
- [ ] **Step 5:** Commit `feat: add LLM client abstraction with Anthropic and fake implementations`.

---

### Task 7: Agent 2 Extract + check_quotes

**Files:**
- Create: `backend/app/ai/agents/extract.py`, `backend/app/ai/agents/check_quotes.py`, `backend/app/ai/prompts/extract/v1.md`
- Test: `tests/backend/unit/test_extract.py`, `tests/backend/unit/test_check_quotes.py`

**Interfaces:**
- Consumes: `LLMClient`, `load_prompt`, `Chunk`, `MeetingContext`, `DialogueAct`.
- Produces:

```python
class RawAct(BaseModel):          # schema LLM trả; không có id/seq/speaker/start/topic_id/due_date
    utterance_id: str; act: Act; quote: str
    topic_hint: str | None = None; option: str | None = None; content: str | None = None
    assignee: str | None = None; due_text: str | None = None; condition: str | None = None
    confidence: float = Field(ge=0, le=1)
class ExtractOutput(BaseModel): acts: list[RawAct]

def render_chunk(chunk: Chunk) -> str      # mỗi dòng: "u0042 [00:47:12] Lan: ..."
async def extract_chunk(llm: LLMClient, ctx: MeetingContext, chunk: Chunk, prompt_version: str) -> list[DialogueAct]
def dedupe_acts(acts: list[DialogueAct]) -> list[DialogueAct]     # khoá (utterance_id, act, option); giữ confidence cao hơn; sắp theo (start, seq)
def check_quotes(acts: list[DialogueAct], utts: dict[str, Utterance]) -> tuple[list[DialogueAct], float]
    # trả (act hợp lệ, tỷ lệ sai); hợp lệ khi fuzz.partial_ratio(quote, utt.text) >= 90 (đã casefold)
```

- `extract_chunk`: `system` = prompt extract + khối ngữ cảnh (tiêu đề, ngày, người tham gia + vai trò + người ra quyết định, glossary); `user` = `render_chunk`. Act có `utterance_id` không thuộc chunk thì bỏ. Code điền `id` (`f"a{seq:04d}_{n}"`), `seq`, `speaker`, `start` từ utterance.
- Prompt `extract/v1.md` phải nêu: định nghĩa 16 act; quy tắc 10.1 ("hay là…", "em nghĩ…" không phải DECIDE; chức vụ không biến ý kiến thành quyết định); quy tắc 10.4 về tri thức; `quote` phải chép nguyên văn một đoạn con của đúng câu đó; `option` là tên phương án ngắn gọn; `due_text` chép nguyên cụm thời gian, không tự tính ngày; câu đùa/giả định → `hypothetical`; một câu có thể sinh nhiều act.

- [ ] **Step 1: Test**

```python
async def test_extract_fills_fields_and_drops_unknown_utterance():
    llm = FakeLLM({"extract": [{"acts": [
        {"utterance_id": "u0001", "act": "propose", "quote": "dùng MongoDB", "option": "MongoDB", "confidence": 0.9},
        {"utterance_id": "u9999", "act": "decide", "quote": "x", "confidence": 0.9}]}]})
    acts = await extract_chunk(llm, CTX, CHUNK, "v1")
    assert len(acts) == 1 and acts[0].speaker == "Minh" and acts[0].start == 20 and acts[0].seq == 1
    assert "u0001 [00:00:20] Minh:" in llm.calls[0][1]

def test_dedupe_overlap_keeps_higher_confidence(): ...   # hai act cùng khoá, conf 0.6 và 0.9 → còn 1, conf 0.9

def test_check_quotes():
    ok, bad_ratio = check_quotes([act_q("u0001", "dùng MongoDB cho nhanh"), act_q("u0001", "dùng Cassandra")], UTTS)
    assert len(ok) == 1 and bad_ratio == 0.5

def test_check_quotes_unknown_utterance_is_invalid(): ...   # utterance_id không có trong UTTS → bị loại
```

- [ ] **Step 2:** Chạy → FAIL. **Step 3:** Viết module + prompt. **Step 4:** Chạy → PASS.
- [ ] **Step 5:** Commit `feat: add extract agent and quote verification`.

---

### Task 8: Agent 3a Topics

**Files:**
- Create: `backend/app/ai/agents/topics.py`, `backend/app/ai/prompts/topics/v1.md`
- Test: `tests/backend/unit/test_topics.py`

**Interfaces:**
- Consumes: `DialogueAct`, `LLMClient`.
- Produces:

```python
TOPIC_ACTS = {PROPOSE, SUPPORT, OBJECT, AMEND, DECIDE, REJECT, DEFER, REOPEN}
class TopicSpec(BaseModel): topic_id: str; question: str
class Assignment(BaseModel): act_id: str; topic_id: str; option: str | None
class TopicsOutput(BaseModel):
    topics: list[TopicSpec]
    aliases: dict[str, str]           # tên gọi khác → tên chuẩn ("Mongo" → "MongoDB")
    assignments: list[Assignment]
async def assign_topics(llm, ctx, acts: list[DialogueAct], prompt_version: str) -> tuple[list[TopicSpec], list[DialogueAct]]
```

- Chỉ gửi act thuộc `TOPIC_ACTS` (dạng `act_id | ts | speaker | act | option | quote`). Act trả về được gán `topic_id` và `option` (đã qua `aliases`). `act_id` lạ hoặc `topic_id` không có trong `topics` thì bỏ qua. Act thuộc `TOPIC_ACTS` không được gán thì giữ `topic_id=None` (không vào máy trạng thái). Act ngoài `TOPIC_ACTS` trả về nguyên vẹn. Không có act nào thuộc `TOPIC_ACTS` → không gọi LLM.
- Prompt nêu: gom theo câu hỏi cần quyết định; gộp tên gọi cùng một phương án; với DECIDE/REJECT/REOPEN không có option, chỉ gán option khi ngữ cảnh rõ ràng, nếu không thì để `null`.

- [ ] **Step 1: Test**

```python
async def test_assign_topics_applies_aliases_and_ignores_unknown():
    llm = FakeLLM({"topics": [{"topics": [{"topic_id": "t1", "question": "CSDL nào?"}],
        "aliases": {"Mongo": "MongoDB"},
        "assignments": [{"act_id": "a1", "topic_id": "t1", "option": "Mongo"},
                        {"act_id": "zzz", "topic_id": "t1", "option": "X"},
                        {"act_id": "a2", "topic_id": "t9", "option": "Y"}]}]})
    specs, out = await assign_topics(llm, CTX, [A1_PROPOSE, A2_SUPPORT, A3_ASSIGN], "v1")
    by = {a.id: a for a in out}
    assert by["a1"].topic_id == "t1" and by["a1"].option == "MongoDB"
    assert by["a2"].topic_id is None and by["a3"] == A3_ASSIGN

async def test_no_topic_acts_skips_llm():
    llm = FakeLLM({})
    assert (await assign_topics(llm, CTX, [A3_ASSIGN], "v1"))[0] == [] and llm.calls == []
```

- [ ] **Step 2:** FAIL → **Step 3:** viết → **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat: add topic grouping agent`.

---

### Task 9: Agent 3d Arbitrate

**Files:**
- Create: `backend/app/ai/agents/arbitrate.py`, `backend/app/ai/prompts/arbitrate/v1.md`
- Test: `tests/backend/unit/test_arbitrate.py`

**Interfaces:**
- Consumes: `Topic`, `MeetingContext`, `Utterance`, `LLMClient`.
- Produces:

```python
def arbitration_reasons(topic: Topic, ctx: MeetingContext) -> list[str]
    # "close_decides": hai DECIDE khác option, |Δstart| < 60
    # "unauthorized_then_object": DECIDE của người không có thẩm quyền (khi có danh sách maker) rồi OBJECT ngay act kế tiếp của chủ đề
    # "object_after_decide": OBJECT sau DECIDE của phương án đang DECIDED, không có REOPEN ở giữa
class Arbitration(BaseModel):
    decided_option: str | None; ambiguous: bool; rationale: str
async def arbitrate(llm, topic: Topic, utts: list[Utterance], reasons: list[str], prompt_version: str) -> Arbitration
def apply_arbitration(topic: Topic, result: Arbitration) -> Topic
```

- `arbitrate` gửi các câu từ act sớm nhất tới act muộn nhất của chủ đề (mở rộng thêm 3 câu mỗi phía) cùng lịch sử từng option.
- `apply_arbitration`: `ambiguous` hoặc `decided_option` không có trong `topic.options` → mọi option DECIDED/SUPERSEDED chuyển `OPEN`, `superseded_by=None`, và đặt `topic.needs_confirmation = True`. `decided_option` trùng với option đang DECIDED → giữ nguyên. Khác → option đó DECIDED (giữ `decided_act` là DECIDE muộn nhất của option đó; không có thì coi là ambiguous), các option khác chưa REJECTED → SUPERSEDED bởi nó.

- [ ] **Step 1: Test**

```python
def test_reasons_close_decides(): assert "close_decides" in arbitration_reasons(topic_of([(D,"A",10),(D,"B",40)]), CTX)
def test_reasons_none_for_clean_a_to_b(): assert arbitration_reasons(run(A_TO_B), CTX) == []
def test_reasons_object_after_decide(): ...      # D A @10, O A @20 → "object_after_decide"
def test_reasons_unauthorized_then_object(): ... # maker = Lan; Minh D A, Hoa O A ngay sau
def test_apply_ambiguous_opens_all(): ...        # mọi option → OPEN, needs_confirmation True
def test_apply_switch_decision(): ...            # A DECIDED, kết luận "B" (B có DECIDE trước đó) → B DECIDED, A SUPERSEDED by B
async def test_arbitrate_calls_llm_with_opus_agent_name(): ...  # FakeLLM key "arbitrate"
```

- [ ] **Step 2:** FAIL → **Step 3:** viết → **Step 4:** PASS (cả test cũ của Task 4).
- [ ] **Step 5:** Commit `feat: add arbitration for conflicting decisions`.

---

### Task 10: Agent 3c Build items + độ tin cậy

**Files:**
- Create: `backend/app/ai/agents/build_items.py`
- Test: `tests/backend/unit/test_build_items.py`

**Interfaces:**
- Consumes: `Topic` (sau run_topic/arbitrate), `TopicSpec`, `DialogueAct`, `MeetingContext`, `resolve_due`, `fmt_ts`.
- Produces:

```python
def norm_name(s: str) -> str          # casefold + gộp khoảng trắng + strip
def decision_confidence(opt: Option, ctx: MeetingContext) -> float   # spec 10.1, so sánh bằng norm_name
def build_items(ctx: MeetingContext, topics: list[Topic], specs: list[TopicSpec],
                acts: list[DialogueAct]) -> list[MeetingItem]
```

- Quy tắc theo bảng spec mục 8.3. Chi tiết đã chốt:
  - `decision`: `content` = `"{question} → {option}"`; `owner` = speaker của `decided_act`; `supersedes` = label các option `superseded_by == option`; `rationale` = nối `quote` của SUPPORT/OBJECT (tối đa 3, ngăn cách "; "); evidence = `decided_act` + PROPOSE đầu tiên của option; `condition` từ `decided_act.condition`. Có condition → thêm `open_question` "Theo dõi điều kiện: {condition}".
  - Chủ đề không có DECIDED → một `open_question` `content=question`, `status=OPEN`, evidence = act đầu tiên của chủ đề. Nếu `topic.needs_confirmation` hoặc (`ambiguous_decides` và không có DECIDED) → cờ `needs_confirmation`; có DECIDED và `ambiguous_decides` → cờ `needs_confirmation` trên `decision`.
  - DEFER: `open_question` (như trên) + nếu act DEFER có `assignee` hoặc người nói tự nhận thì `action_item` `"Xin ý kiến: {question}"`, owner = assignee hoặc speaker.
  - Giao việc: nhóm `ASSIGN`/`ACCEPT_TASK` theo `content` gần giống nhau (`fuzz.token_set_ratio ≥ 80`) hoặc ACCEPT_TASK đứng ngay sau ASSIGN (≤ 2 câu) thì cùng nhóm; owner/due lấy theo act mới nhất có giá trị; `ACCEPT_TASK` không có assignee → owner = speaker; `due_date = resolve_due(due_text, ctx.meeting_date)`.
  - `RAISE_BLOCKER`/`REQUEST`/`FEEDBACK`/`KNOWLEDGE` → loại tương ứng; `requester` của request = `act.assignee` nếu LLM điền (người/bộ phận yêu cầu), không có thì speaker.
  - `ASK` không thuộc chủ đề nào và không có act nào của câu sau nó trả lời (không có act cùng `topic_hint` trong 3 câu sau) → `open_question`.
  - `HYPOTHETICAL` → bỏ.
  - `id` mục: `f"{ctx.meeting_id}-i{n:03d}"` theo thứ tự xuất hiện; `confidence` của mục không phải decision = trung bình confidence của các act nguồn.

- [ ] **Step 1: Test** (mỗi dòng bảng 8.3 một test; tên test nêu rõ dòng), tối thiểu:

```python
def test_decided_topic_makes_final_decision_with_supersedes(): ...   # Postgres FINAL, owner Lan, supersedes ["MongoDB"]
def test_undecided_topic_makes_open_question(): ...
def test_conditional_decision_adds_followup_question(): ...
def test_defer_makes_question_and_ask_permission_task(): ...
def test_assign_then_accept_merged_with_resolved_due():
    # ASSIGN "Dựng schema Postgres" assignee Minh due_text "thứ Sáu tuần sau" + ACCEPT_TASK của Minh
    items = build_items(CTX_0810, [], [], acts)
    [ai] = [i for i in items if i.type == ItemType.ACTION_ITEM]
    assert ai.owner == "Minh" and ai.due_date == date(2026, 10, 16)
def test_hypothetical_dropped(): ...
def test_decision_confidence_penalties():
    assert decision_confidence(opt_decided_by("Minh", 1.0), CTX_MAKER_LAN) == 0.85
    assert decision_confidence(opt_decided_by("lan ", 1.0, object_after=True), CTX_MAKER_LAN) == 0.6
def test_ambiguous_decide_flags_needs_confirmation(): ...
```

- [ ] **Step 2:** FAIL → **Step 3:** viết → **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat: add item builder and decision confidence`.

---

### Task 11: Agent 4 Validate

**Files:**
- Create: `backend/app/ai/agents/validate.py`
- Test: `tests/backend/unit/test_validate.py`

**Interfaces:**
- Produces: `validate_items(items: list[MeetingItem]) -> list[MeetingItem]`.
- Quy tắc spec 10.5: thêm `missing_owner`, `missing_due_date`, `missing_requester`, `low_confidence` (< 0.6); mục `evidence` rỗng bị bỏ; mục trùng (cùng `type` và `fuzz.token_set_ratio(content) ≥ 90`) gộp: giữ mục có confidence cao hơn, nối evidence không trùng `utterance_id`, hợp nhất flags. Sắp xếp: mục có cờ trước, rồi theo `ts` của evidence đầu tiên. Không thêm cờ đã có.

- [ ] **Step 1: Test**

```python
def test_action_item_missing_fields_flagged(): assert set(validate_items([ai(owner=None, due=None)])[0].flags) == {"missing_owner", "missing_due_date"}
def test_low_confidence_threshold():
    assert "low_confidence" in validate_items([dec(conf=0.59)])[0].flags
    assert "low_confidence" not in validate_items([dec(conf=0.6)])[0].flags
def test_item_without_evidence_dropped(): assert validate_items([dec(evidence=[])]) == []
def test_duplicates_merged(): ...
def test_flagged_items_sorted_first(): ...
```

- [ ] **Step 2:** FAIL → **Step 3:** viết → **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat: add item validation`.

---

### Task 12: Pipeline LangGraph

**Files:**
- Create: `backend/app/ai/pipeline.py`
- Create fixtures: `tests/fixtures/transcripts/payment_v2.txt` (spec mục 16), `tests/fixtures/llm/payment_v2/{extract.json,topics.json}` (phản hồi viết tay đúng như một LLM tốt trả về cho transcript này)
- Test: `tests/backend/integration/test_pipeline_fake.py`

**Interfaces:**
- Consumes: mọi agent ở Task 3–11.
- Produces:

```python
ProgressFn = Callable[[str, float], Awaitable[None]]       # (step, progress 0..1)
class AnalysisResult(BaseModel):
    utterances: list[Utterance]; acts: list[DialogueAct]; topics: list[Topic]
    specs: list[TopicSpec]; items: list[MeetingItem]
async def analyze_transcript(*, ctx: MeetingContext, filename: str, data: bytes, llm: LLMClient,
                             settings: AISettings, on_progress: ProgressFn | None = None) -> AnalysisResult
```

- Đồ thị đúng như spec 8.1. State của graph là `TypedDict` (`utterances`, `chunks`, `acts_by_chunk`, `retried: set[int]`, `topics`, `specs`, `items`). Node `extract` chạy song song các chunk cần chạy với `asyncio.Semaphore(settings.max_concurrency)`. Node `check_quotes` tính tỷ lệ sai theo từng chunk; conditional edge quay lại `extract` chỉ cho các chunk có tỷ lệ sai > 0.3 và chưa có trong `retried`. Sau đó `dedupe_acts` trên toàn bộ act hợp lệ.
- `state_machine`: `run_topic` cho mỗi `TopicSpec` với act có `topic_id` tương ứng; `arbitrate` chỉ gọi cho chủ đề có `arbitration_reasons` không rỗng.
- Tiến trình: gọi `on_progress` khi vào mỗi node với các bước `normalize, extract, check_quotes, topics, state_machine, arbitrate, build_items, validate` và progress tăng dần, cuối cùng `("done", 1.0)`.
- Lỗi: `TranscriptParseError` để nguyên; mọi `LLMError` bọc thành `AnalysisError(step=<node>)`.

- [ ] **Step 1: Test**

```python
async def test_payment_v2_end_to_end_with_fake_llm():
    res = await analyze_transcript(ctx=CTX_PAYMENT, filename="payment_v2.txt", data=PAYMENT, llm=fake_from_fixtures(), settings=AISettings())
    dec = [i for i in res.items if i.type == ItemType.DECISION]
    assert len(dec) == 1 and "Postgres" in dec[0].content and dec[0].supersedes == ["MongoDB"] and dec[0].owner == "Lan"
    ai = {i.content: i for i in res.items if i.type == ItemType.ACTION_ITEM}
    assert any(i.owner == "Minh" and i.due_date == date(2026, 10, 16) for i in ai.values())
    assert not any("hoàn tiền" in e.quote for i in res.items for e in i.evidence)
    assert {i.type for i in res.items} >= {ItemType.BLOCKER, ItemType.REQUEST, ItemType.OPEN_QUESTION, ItemType.KNOWLEDGE, ItemType.FEEDBACK}

async def test_retry_once_when_quotes_bad():
    # extract trả lần 1 toàn quote bịa, lần 2 đúng → 2 lời gọi extract; lần 3 không bao giờ xảy ra
async def test_retry_only_once_even_if_still_bad(): ...           # 2 lời gọi, act sai bị loại, không lỗi
async def test_no_decisions_meeting_returns_items_without_error(): ...   # extract chỉ trả feedback
async def test_long_transcript_respects_concurrency():
    llm = FakeLLM({"extract": [{"acts": []}] * 11})
    await analyze_transcript(ctx=CTX, filename="long.txt", data=make_txt(400), llm=llm, settings=AISettings(max_concurrency=4))
    assert len([c for c in llm.calls if c[0] == "extract"]) == 11 and llm.max_in_flight <= 4
async def test_llm_error_wrapped_with_step(): ...                  # FakeLLM callable raise LLMError trong "topics" → AnalysisError.step == "topics"
async def test_progress_reported_in_order(): ...
```

- [ ] **Step 2:** FAIL → **Step 3:** viết pipeline + fixtures → **Step 4:** PASS; chạy cả bộ `uv run pytest` xanh, `ruff`, `mypy app` sạch.
- [ ] **Step 5:** Commit `feat: add LangGraph analysis pipeline`.

---

### Task 13: Metrics và runner eval

**Files:**
- Create: `evals/__init__.py`, `evals/config.yaml`, `evals/metrics/__init__.py`, `evals/metrics/matching.py`, `evals/metrics/scores.py`, `evals/runners/__init__.py`, `evals/runners/run_pipeline.py`, `evals/datasets/transcripts/payment_v2.txt`, `evals/golden/payment_v2.json`
- Test: `tests/backend/unit/test_eval_metrics.py`

**Interfaces:**
- Golden JSON:

```json
{"context": { MeetingContext },
 "transcript": "datasets/transcripts/payment_v2.txt",
 "kind": "realistic | trap",
 "topics": [{"question": "CSDL cho dịch vụ thanh toán", "final_option": "PostgreSQL", "match": ["postgres"]}],
 "items": [{"type": "decision", "content": "Dùng PostgreSQL cho dịch vụ thanh toán", "match": ["postgres"],
            "owner": "Lan", "due_date": null, "status": "final"}]}
```

  `match`: danh sách từ khoá (casefold, không dấu) mà nội dung mục dự đoán phải chứa ít nhất một — nhờ vậy so khớp tiếng Việt diễn đạt khác nhau vẫn ổn định mà không cần LLM chấm.
- Produces:

```python
def strip_accents(s: str) -> str
def match_items(pred: list[MeetingItem], gold: list[GoldItem]) -> list[tuple[int, int]]
    # ghép tham lam: cùng type và chứa một từ khoá match; ưu tiên fuzz.token_set_ratio cao nhất; mỗi mục ghép tối đa một lần
def score_meeting(res: AnalysisResult, golden: Golden, transcript_utts: list[Utterance]) -> MeetingScore
class MeetingScore(BaseModel):
    per_type: dict[str, tuple[int, int, int]]   # (tp, n_pred, n_gold)
    final_decision_correct: int; final_decision_total: int
    owner_due_correct: int; owner_due_total: int
    evidence_ok: int; evidence_total: int
    trap_correct: bool | None                     # chỉ cho kind == "trap": mọi topic đúng final_option
def aggregate(scores: list[MeetingScore]) -> dict[str, float]     # các chỉ số và ngưỡng spec 13.2
```

  "Quyết định cuối đúng" cho mỗi topic golden: nếu `final_option` khác null thì đúng khi có **đúng một** decision FINAL chứa một từ khoá trong `match` của topic; nếu `final_option` là null thì đúng khi **không** decision nào chứa các từ khoá đó. Evidence đúng: `partial_ratio(quote, utterance.text) ≥ 90` với utterance cùng id.
- `run_pipeline.py`: `python -m evals.runners.run_pipeline [--prompt-version v1] [--only NAME] [--kind trap|realistic]`; đọc mọi `evals/golden/*.json`, chạy `analyze_transcript` với `AnthropicLLM`, in bảng chỉ số so với ngưỡng, ghi `evals/reports/<timestamp>.json` (cả item dự đoán để debug), exit code 1 nếu dưới ngưỡng. Ngưỡng đọc từ `evals/config.yaml`.

- [ ] **Step 1: Test**

```python
def test_match_items_by_type_and_keyword(): ...    # decision "Chốt dùng Postgres" khớp gold match ["postgres"]; blocker không khớp decision
def test_strip_accents(): assert strip_accents("Hoá đơn") == "hoa don"
def test_aggregate_thresholds():
    agg = aggregate([perfect_score(), half_recall_score()])
    assert agg["recall"] == pytest.approx(0.75) and agg["pass"] is True
def test_trap_incorrect_when_any_topic_wrong(): ...
```

- [ ] **Step 2:** FAIL → **Step 3:** viết; golden `payment_v2.json` chép từ bảng spec mục 16 (11 dòng, dòng HYPOTHETICAL không vào `items`) → **Step 4:** PASS.
- [ ] **Step 5:** Chạy thật: `PYTHONPATH=backend uv run --project backend python -m evals.runners.run_pipeline --only payment_v2` (cần `ANTHROPIC_API_KEY`). Kỳ vọng: ≥ 8/10 mục khớp golden. Chưa đạt thì chỉnh `prompts/*/v1.md` và chạy lại; ghi số đạt được vào commit message.
- [ ] **Step 6:** Commit `feat: add eval metrics and pipeline runner`.

---

### Task 14: Bộ kịch bản bẫy và transcript thực tế

**Files:**
- Create: `evals/datasets/synthetic/*.txt`, `evals/datasets/transcripts/*.txt`, `evals/golden/*.json`

**Interfaces:** định dạng golden ở Task 13.

- [ ] **Step 1:** Viết 10 transcript bẫy tiếng Việt (8–20 câu mỗi bài, ngày họp và người ra quyết định ghi trong `context`), mỗi bài một kịch bản: `a_to_b`, `b_back_to_a`, `decide_a_then_b`, `reject_decided`, `ambiguous_decide` (hai phương án rồi "ok chốt vậy" → open_question + needs_confirmation), `conditional_decide`, `wait_for_boss` (DEFER), `joke_hypothetical`, `implicit_assignment` ("cái này để em lo"), `relative_deadlines` (≥ 3 kiểu hạn chót ở mục 10.6). Golden mỗi bài có `topics` và `items`.
- [ ] **Step 2:** Viết thêm 4 transcript thực tế 30–60 câu (họp sprint, họp với khách hàng, post-mortem sự cố, họp tuyển dụng), mỗi bài có ít nhất một chủ đề đổi phương án.
- [ ] **Step 3:** Chạy `... run_pipeline` trên toàn bộ dataset; ghi bảng chỉ số vào `evals/README.md` (ngày, prompt version, model, từng chỉ số so với ngưỡng). Mục tiêu: kịch bản bẫy 1.00, còn lại theo spec 13.2; chưa đạt thì lặp chỉnh prompt (tối đa 3 vòng), sau đó ghi rõ chỉ số nào chưa đạt.
- [ ] **Step 4:** **Dừng và nhờ người dùng xem lại golden** (spec 13.2: golden phải được người xác nhận). Liệt kê file cần xem.
- [ ] **Step 5:** Commit `feat: add trap scenarios and realistic eval transcripts`.

---

## Kiểm tra cuối kế hoạch

- [ ] `cd backend && uv run pytest` xanh; `uv run ruff check .` và `uv run mypy app` sạch.
- [ ] `grep -rE "fastapi|sqlalchemy|redis" backend/app/ai` không có kết quả.
- [ ] Báo cáo eval đầu tiên nằm trong `evals/README.md`.
