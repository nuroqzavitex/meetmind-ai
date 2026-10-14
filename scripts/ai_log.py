"""Collect the prompts sent to Claude Code for this project into ai-log.txt.

Reads the session transcripts Claude Code keeps under ~/.claude/projects/<project-dir>/*.jsonl and
writes every prompt typed by the user (plus answers picked in multiple-choice questions), oldest
first. Usage: python scripts/ai_log.py [output-file]   (normally run through update-ai-log.sh)
"""

import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKIP_PREFIXES = (
    "<local-command", "<command-", "<system-reminder", "Caveat:", "[Request interrupted",
    "This session is being continued", "<task-notification", "<bash-",
)
SKIP_COMMANDS = {"/compact", "/clear", "/model", "/cost", "/help", "/status", "/config"}


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


def text_of(content: object) -> tuple[str | None, bool]:
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


def clean(t: str) -> str:
    for tag in ("system-reminder", "ide_opened_file", "ide_selection"):
        t = re.sub(rf"<{tag}>.*?</{tag}>", "", t, flags=re.S)
    t = re.sub(r"\[Image: source:[^\]]*\]", "", t)
    return t.strip()


def collect(folder: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for f in sorted(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime):
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
            raw, has_image = text_of(content)
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
                t = clean(raw)
                if not t or t.startswith(SKIP_PREFIXES):
                    continue
            if has_image:
                t = f"[kèm ảnh chụp màn hình] {t}".strip()
            rows.append((d.get("timestamp", ""), t))
    seen: set[tuple[str, str]] = set()
    return [r for r in sorted(rows, key=lambda r: r[0]) if not (r in seen or seen.add(r))]


def main() -> None:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "ai-log.txt"
    rows = collect(transcript_dir())
    lines = [
        "AI LOG - MeetMind AI",
        "Tổng hợp các prompt người phát triển đã gửi cho trợ lý AI (Claude Code) trong quá trình xây dựng dự án.",
        "Thứ tự theo thời gian. Ảnh chụp màn hình không được lưu, chỉ ghi chú [kèm ảnh chụp màn hình].",
        f"Tổng số prompt: {len(rows)}",
        "=" * 80,
        "",
    ]
    for i, (ts, t) in enumerate(rows, 1):
        lines += [f"[{i:03d}] {ts[:16].replace('T', ' ') + ' UTC' if ts else ''}", t, "-" * 80]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Đã ghi {len(rows)} prompt vào {out_path}")


if __name__ == "__main__":
    main()
