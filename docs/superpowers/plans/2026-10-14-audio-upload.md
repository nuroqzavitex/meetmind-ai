# Audio upload Implementation Plan

> Executed inline (superpowers:executing-plans) on branch `feat/audio-upload`.

**Goal:** Upload meeting audio → diarized transcript → user maps speakers → existing analysis.
**Spec:** `docs/superpowers/specs/2026-10-14-audio-upload-design.md`

## Global Constraints

- Commits carry only the user's identity (no Co-Authored-By, no "Generated with Claude Code"). Never run `ruff format`.
- `tests/` never call real APIs: STT goes through `FakeSTT`.
- Vietnamese UI/messages; English code/commits. Generated transcript lines: `[HH:MM:SS] <speaker>: <text>`.
- Statuses: `transcribing`, `awaiting_speakers`. Job kind: `transcribe`. Labels: `Người nói A`, `Người nói B`, …
- Audio extensions: `.mp3 .m4a .wav .webm .mp4 .mpeg .mpga`; `MAX_AUDIO_BYTES=25_000_000`; `STT_MODEL=gpt-4o-transcribe-diarize`.

## Review Focus

1. Speaker name containing `:` or empty → would corrupt the txt line format → 422.
2. POST speakers twice / while analyzing → 409, no second analyze job.
3. Audio upload over 25 MB vs transcript over 5 MB → 413 with the right limit for each type.
4. STT returns zero segments → job fails with a clear message, meeting `failed`, reanalyze retries transcription.
5. Org B calling speakers endpoints on org A's meeting → 404.

### Task 1: STT module + transcript building (`backend/app/ai/stt/`)
- `Segment(speaker: str, start: float, end: float | None, text: str)`; `SpeechToText` protocol `async transcribe(filename, data) -> list[Segment]`.
- `OpenAISTT(client, model)`, `FakeSTT(segments)`, `UnconfiguredSTT` (raises `STTError("OPENAI_API_KEY chưa được cấu hình")`).
- `is_audio(filename) -> bool`; `label_speakers(segments) -> list[Segment]` (A, B… by first appearance, drop empty text);
  `to_transcript_txt(segments) -> bytes`; `rename_speakers(txt: bytes, mapping: dict[str, str]) -> bytes`;
  `speaker_summary(txt: bytes) -> list[(label, count, samples)]`.
- Tests: `tests/backend/unit/test_stt.py`.

### Task 2: Backend flow
- Settings `stt_model`, `max_audio_bytes`; `core/stt.py::build_stt(settings)`.
- `create_meeting`: audio → size check vs `max_audio_bytes`, status `transcribing`, job `transcribe`; endpoint reads up to the larger limit.
- `services/transcription.py::run_transcription(sm, stt, ...)`; worker function `transcribe`.
- `services/speakers.py`: `get_speakers`, `assign_speakers`; endpoints in `meetings.py`; schemas.
- `reanalyze`: audio source → transcribe. `get_meeting`: job kind by status/source.
- Tests: `tests/backend/api/test_audio_flow.py`, isolation cases.

### Task 3: Frontend
- Types regen (`npm run gen:types`), status labels/styles, upload form audio, `/meetings/[id]/speakers` page + hooks,
  JobProgress navigation for transcribe jobs, meeting list link.
- Tests: `tests/features/meetings/*`, `tests/features/speakers/*`.

### Task 4: Docs + verification
- README/docs/CLAUDE.md, `.env.example`, `render.yaml` (STT_MODEL), full test suites, final review.
