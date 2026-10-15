"""Minimal Clerk Backend API client (needs CLERK_SECRET_KEY)."""

from typing import Any

import httpx
from pydantic import BaseModel

BASE_URL = "https://api.clerk.com/v1"


class ClerkError(Exception):
    """Clerk rejected the call or could not be reached."""


class ClerkUnavailable(ClerkError):
    """No secret key configured."""


class ClerkUser(BaseModel):
    name: str
    email: str | None = None


class ClerkAPI:
    def __init__(
        self,
        secret_key: str | None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._key = secret_key
        self._transport = transport
        self._timeout = timeout

    async def _call(self, method: str, path: str, json: Any = None) -> httpx.Response:
        if not self._key:
            raise ClerkUnavailable("CLERK_SECRET_KEY chưa được cấu hình")
        try:
            async with httpx.AsyncClient(
                base_url=BASE_URL,
                transport=self._transport,
                timeout=self._timeout,
                headers={"Authorization": f"Bearer {self._key}"},
            ) as c:
                return await c.request(method, path, json=json)
        except httpx.HTTPError as exc:
            raise ClerkError("Không kết nối được tới Clerk") from exc

    async def get_user(self, user_id: str) -> ClerkUser:
        r = await self._call("GET", f"/users/{user_id}")
        if r.status_code != 200:
            raise ClerkError(f"Clerk trả lỗi khi đọc người dùng (HTTP {r.status_code})")
        data = r.json()
        primary = data.get("primary_email_address_id")
        emails = data.get("email_addresses") or []
        email = next((e.get("email_address") for e in emails if e.get("id") == primary), None)
        if email is None and emails:
            email = emails[0].get("email_address")
        name = " ".join(p for p in (data.get("first_name"), data.get("last_name")) if p)
        return ClerkUser(name=name or data.get("username") or email or user_id, email=email)

    async def get_org_name(self, org_id: str) -> str:
        r = await self._call("GET", f"/organizations/{org_id}")
        if r.status_code != 200:
            raise ClerkError(f"Clerk trả lỗi khi đọc tổ chức (HTTP {r.status_code})")
        name = r.json().get("name")
        return name if isinstance(name, str) and name else org_id

    async def member_org_ids(self, user_id: str) -> set[str]:
        """Ids of the organizations the user belongs to right now."""
        r = await self._call("GET", f"/users/{user_id}/organization_memberships?limit=100")
        if r.status_code != 200:
            raise ClerkError(f"Clerk trả lỗi khi đọc tổ chức của người dùng (HTTP {r.status_code})")
        return {
            org["id"]
            for m in r.json().get("data") or []
            if isinstance(org := m.get("organization"), dict) and isinstance(org.get("id"), str)
        }

    async def add_member(self, org_id: str, user_id: str) -> None:
        r = await self._call(
            "POST",
            f"/organizations/{org_id}/memberships",
            json={"user_id": user_id, "role": "org:member"},
        )
        if r.status_code in (200, 201):
            return
        try:
            errors = r.json().get("errors") or []
        except ValueError:
            errors = []
        if any(e.get("code") == "already_a_member_in_organization" for e in errors):
            return
        raise ClerkError(f"Clerk không thêm được thành viên (HTTP {r.status_code})")
