"""Collect the prompts sent to Claude Code for this project, review them, then keep them in ai-log.txt.

    python scripts/ai_log.py collect   # new prompts -> ai-log-temp.txt (delete the ones to drop)
    python scripts/ai_log.py commit    # entries left in ai-log-temp.txt -> end of ai-log.txt, temp emptied

Prompts come from the session transcripts Claude Code keeps under ~/.claude/projects/<project-dir>/.
Both files carry a "Đã duyệt đến:" line (the newest transcript timestamp already shown), so a prompt
deleted during review never comes back. Normally run through scripts/update-ai-log.sh.
"""

import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOG = REPO / "ai-log.txt"
TEMP = REPO / "ai-log-temp.txt"
SEP = "-" * 80
MARK = "Đã duyệt đến: "
HEADER_RE = re.compile(r"^\[(\d+)\] (.*)$")
SKIP_PREFIXES = (
    "<local-command", "<command-", "<system-reminder", "Caveat:", "[Request interrupted",
    "This session is being continued", "<task-notification", "<bash-",
)
SKIP_COMMANDS = {"/compact", "/clear", "/model", "/cost", "/help", "/status", "/config"}


# --- reading the transcripts ---


def transcript_dir() -> Path:
    """~/.claude/projects/<repo path with ':', '\\' and '/' replaced by '-'>, matched case-insensitively."""
    override = os.environ.get("CLAUDE_PROJECT_DIR")
    if override:
        return Path(override)
    root = Path.home() / ".claude" / "projects"
    want = re.sub(r"[:\\/]", "-", str(REPO)).casefold()
    for d in root.iterdir() if root.is_dir() else []:
        if d.is_dir() and d.name.casefold() == want:
            return d
    sys.exit(f"Không tìm thấy thư mục transcript cho {REPO} trong {root} (đặt CLAUDE_PROJECT_DIR).")


def _text_of(content: object) -> tuple[str | None, bool]:
    if isinstance(content, str):
        return content, False
    parts, has_image = [], False
    for c in content if isinstance(content, list) else []:
        if c.get("type") == "text":
            parts.append(c["text"])
        elif c.get("type") == "image":
            has_image = True
        elif c.get("type") == "tool_result":
            return None, False
    return "\n".join(parts), has_image


def _clean(t: str) -> str:
    for tag in ("system-reminder", "ide_opened_file", "ide_selection"):
        t = re.sub(rf"<{tag}>.*?</{tag}>", "", t, flags=re.S)
    t = re.sub(r"\[Image: source:[^\]]*\]", "", t)
    return t.strip()


def transcript_prompts() -> list[tuple[str, str]]:
    """(ISO timestamp, prompt text), oldest first."""
    rows: list[tuple[str, str]] = []
    for f in sorted(transcript_dir().glob("*.jsonl"), key=lambda p: p.stat().st_mtime):
        ask_ids: set[str] = set()
        for line in f.open(encoding="utf-8"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            content = (d.get("message") or {}).get("content")
            if d.get("type") == "assistant" and isinstance(content, list):
                ask_ids |= {x["id"] for x in content
                            if x.get("type") == "tool_use" and x.get("name") == "AskUserQuestion"}
            if d.get("type") == "user" and isinstance(content, list):
                for x in content:
                    if x.get("type") == "tool_result" and x.get("tool_use_id") in ask_ids:
                        r = x.get("content")
                        if not isinstance(r, str):
                            r = " ".join(y.get("text", "") for y in r or [] if isinstance(y, dict))
                        m = re.search(r'answered: "(.*)"="(.*?)"\.', r, flags=re.S)
                        if m:
                            rows.append((d.get("timestamp", ""), "[Trả lời câu hỏi lựa chọn] "
                                         f"{m.group(1).strip()}\n=> {m.group(2).strip()}"))
            if d.get("type") != "user" or d.get("isMeta") or d.get("isCompactSummary"):
                continue
            if (d.get("message") or {}).get("role") != "user":
                continue
            raw, has_image = _text_of(content)
            if raw is None:
                continue
            cmd = re.search(r"<command-name>(/[^<]+)</command-name>", raw)
            if cmd:
                name = cmd.group(1).strip()
                if name in SKIP_COMMANDS:
                    continue
                args = re.search(r"<command-args>(.*?)</command-args>", raw, flags=re.S)
                t = f"{name} {args.group(1).strip() if args else ''}".strip()
            else:
                t = _clean(raw)
                if not t or t.startswith(SKIP_PREFIXES):
                    continue
            if has_image:
                t = f"[kèm ảnh chụp màn hình] {t}".strip()
            rows.append((d.get("timestamp", ""), t))
    seen: set[tuple[str, str]] = set()
    return [r for r in sorted(rows, key=lambda r: r[0]) if not (r in seen or seen.add(r))]


# --- the two text files ---


def _when(ts: str) -> str:
    return ts[:16].replace("T", " ") + " UTC" if ts else ""


def read_file(path: Path) -> tuple[str, list[tuple[str, str]]]:
    """(reviewed-up-to timestamp or "", [(display time, text)]) of ai-log.txt / ai-log-temp.txt."""
    if not path.exists():
        return "", []
    mark, entries, block = "", [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(MARK) and block is None:
            mark = line[len(MARK):].strip()
            continue
        m = HEADER_RE.match(line)
        if m and block is None:
            block = [m.group(2).strip()]
        elif line == SEP and block is not None:
            entries.append((block[0], "\n".join(block[1:]).strip()))
            block = None
        elif block is not None:
            block.append(line)
    if block is not None:  # last entry without its separator
        entries.append((block[0], "\n".join(block[1:]).strip()))
    return mark, [e for e in entries if e[1]]


def write_file(path: Path, intro: list[str], mark: str, entries: list[tuple[str, str]]) -> None:
    lines = [*intro, f"Số mục: {len(entries)}", f"{MARK}{mark}", "=" * 80, ""]
    for i, (when, text) in enumerate(entries, 1):
        lines += [f"[{i:03d}] {when}", text, SEP]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


LOG_INTRO = [
    "AI LOG - MeetMind AI",
    "Các prompt người phát triển đã gửi cho trợ lý AI (Claude Code) trong quá trình xây dựng dự án.",
    "Thứ tự theo thời gian. Ảnh chụp màn hình không được lưu, chỉ ghi chú [kèm ảnh chụp màn hình].",
]
TEMP_INTRO = [
    "AI LOG - CHỜ DUYỆT",
    "Prompt mới chưa có trong ai-log.txt. Xoá cả khối (từ dòng [số] đến dòng gạch ngang) của mục không muốn giữ,",
    "rồi chạy: sh scripts/update-ai-log.sh commit. Mục đã xoá sẽ không bị gom lại lần sau.",
]


def _log_mark(log_mark: str, log_entries: list[tuple[str, str]], rows: list[tuple[str, str]]) -> str:
    """Reviewed-up-to of ai-log.txt; older logs without the line: newest prompt already in it."""
    if log_mark:
        return log_mark
    kept = set(log_entries)
    return max((ts for ts, t in rows if (_when(ts), t) in kept), default="")


def collect() -> None:
    rows = transcript_prompts()
    log_mark, log_entries = read_file(LOG)
    temp_mark, temp_entries = read_file(TEMP)
    since = max(_log_mark(log_mark, log_entries, rows), temp_mark)
    new = [(ts, t) for ts, t in rows if ts > since]
    if not new:
        print(f"Không có prompt mới. {TEMP.name} có {len(temp_entries)} mục chờ duyệt.")
        return
    entries = temp_entries + [(_when(ts), t) for ts, t in new]
    write_file(TEMP, TEMP_INTRO, new[-1][0], entries)
    print(f"Thêm {len(new)} prompt mới vào {TEMP.name} ({len(entries)} mục chờ duyệt).")
    print(f"Xoá mục không muốn giữ rồi chạy: sh scripts/update-ai-log.sh commit")


def commit() -> None:
    temp_mark, temp_entries = read_file(TEMP)
    if not temp_mark and not temp_entries:
        print(f"{TEMP.name} đang trống, chưa có gì để đẩy. Chạy: sh scripts/update-ai-log.sh")
        return
    log_mark, log_entries = read_file(LOG)
    mark = max(_log_mark(log_mark, log_entries, transcript_prompts()), temp_mark)
    entries = log_entries + temp_entries
    write_file(LOG, LOG_INTRO, mark, entries)
    TEMP.write_text("", encoding="utf-8")
    print(f"Đã thêm {len(temp_entries)} mục vào {LOG.name} (tổng {len(entries)}). {TEMP.name} đã được làm trống.")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "collect"
    if cmd == "collect":
        collect()
    elif cmd == "commit":
        commit()
    else:
        sys.exit("Dùng: ai_log.py [collect|commit]")


if __name__ == "__main__":
    main()
