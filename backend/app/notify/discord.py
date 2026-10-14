"""Discord webhook delivery and URL validation."""

import re
from typing import Any

import httpx

# Only Discord's own webhook endpoints: the server never posts to an arbitrary user-supplied host.
_WEBHOOK_RE = re.compile(r"^https://(?:discord|discordapp)\.com/api/webhooks/\d+/[\w-]+$")


_INVITE_RE = re.compile(
    r"^https://(?:discord\.gg|(?:www\.)?(?:discord|discordapp)\.com/invite)/[A-Za-z0-9-]{2,32}$"
)


def is_invite_url(url: str) -> bool:
    return _INVITE_RE.fullmatch(url) is not None


def is_webhook_url(url: str) -> bool:
    return _WEBHOOK_RE.fullmatch(url) is not None


def webhook_hint(url: str) -> str:
    """A non-secret hint for the UI: the token's last 4 characters."""
    return f"…{url[-4:]}"


class DiscordError(Exception):
    """Discord could not be reached or rejected the message."""


class DiscordClient:
    def __init__(
        self, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 10.0
    ) -> None:
        self._transport = transport
        self._timeout = timeout

    async def send(self, url: str, payload: dict[str, Any]) -> None:
        # Message text comes from transcripts: never let it ping @everyone or roles.
        body = {**payload, "allowed_mentions": {"parse": []}}
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout) as c:
                r = await c.post(url, json=body)
        except httpx.HTTPError as exc:
            raise DiscordError("Không kết nối được tới Discord") from exc
        if r.status_code in (401, 404):
            raise DiscordError("Webhook không còn tồn tại hoặc đã bị xoá trên Discord")
        if r.status_code >= 400:
            raise DiscordError(f"Discord từ chối tin nhắn (HTTP {r.status_code})")
