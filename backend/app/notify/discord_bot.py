"""Discord slash-command bot: request signatures, permission bits and answer rendering (no I/O)."""

from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.notify.messages import COLOR
from app.schemas.qa import QAResponse

# Interaction and response types (Discord API v10).
PING = 1
APPLICATION_COMMAND = 2
PONG = 1
CHANNEL_MESSAGE = 4
DEFERRED_CHANNEL_MESSAGE = 5
EPHEMERAL = 1 << 6

ADMINISTRATOR = 1 << 3
MANAGE_GUILD = 1 << 5

ASK_COMMAND = "hoi"
LINK_COMMAND = "ketnoi"
AGENDA_COMMAND = "chuongtrinh"
TASKS_COMMAND = "viec"
DECISIONS_COMMAND = "quyetdinh"
OVERVIEW_COMMANDS = (AGENDA_COMMAND, TASKS_COMMAND, DECISIONS_COMMAND)

MAX_ANSWER = 4000
MAX_QUOTE = 160
MAX_SOURCES = 8


def verify_signature(public_key_hex: str, signature_hex: str, timestamp: str, body: bytes) -> bool:
    """Discord signs `timestamp + raw body` with the application's Ed25519 key."""
    try:
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        key.verify(bytes.fromhex(signature_hex), timestamp.encode() + body)
    except (ValueError, InvalidSignature):
        return False
    return True


def can_manage_server(permissions: str | None) -> bool:
    try:
        bits = int(permissions or "0")
    except ValueError:
        return False
    return bool(bits & (ADMINISTRATOR | MANAGE_GUILD))


def option(data: dict[str, Any], name: str) -> str:
    for o in data.get("options") or []:
        if o.get("name") == name and isinstance(o.get("value"), str):
            return str(o["value"]).strip()
    return ""


def ephemeral(text: str) -> dict[str, Any]:
    return {
        "type": CHANNEL_MESSAGE,
        "data": {"content": text, "flags": EPHEMERAL, "allowed_mentions": {"parse": []}},
    }


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def answer_message(question: str, result: QAResponse, app_url: str) -> dict[str, Any]:
    """Public answer: the question, the answer with its [n] markers, and the cited sources."""
    lines = []
    for c in result.citations[:MAX_SOURCES]:
        url = f"{app_url}/meetings/{c.meeting_id}/minutes"
        lines.append(
            f"**[{c.ref}]** [{_clip(c.title, 60)}]({url}) · {c.date.strftime('%d/%m/%Y')} · {c.ts} · "
            f"{_clip(c.speaker, 30)} — “{_clip(c.quote, MAX_QUOTE)}”"
        )
    embed: dict[str, Any] = {
        "title": _clip(f"❓ {question}", 250),
        "description": result.answer[:MAX_ANSWER],
        "color": COLOR,
    }
    sources = ""
    for line in lines:  # whole lines only, within the 1024-character field limit
        if len(sources) + len(line) + 1 > 1024:
            break
        sources += line + "\n"
    if sources:
        embed["fields"] = [{"name": "Nguồn", "value": sources.rstrip()}]
    return {"content": "", "embeds": [embed], "allowed_mentions": {"parse": []}}


def error_message(text: str) -> dict[str, Any]:
    return {"content": f"⚠️ {text}", "embeds": [], "allowed_mentions": {"parse": []}}
