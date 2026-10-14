"""Clerk session-token verification and the `get_principal` dependency."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import jwt
from fastapi import Request
from pydantic import BaseModel

from app.core.errors import Forbidden, ServiceUnavailable, Unauthorized

_REFETCH_INTERVAL = 60.0  # unknown-kid refetch after a successful load
_INITIAL_RETRY_INTERVAL = 5.0  # retry gap while keys have never loaded

log = logging.getLogger(__name__)


class User(BaseModel):
    """A signed-in Clerk user, with or without an active organization."""

    user_id: str
    name: str
    org_id: str | None = None
    org_role: str | None = None


class Principal(BaseModel):
    user_id: str
    org_id: str
    name: str
    org_role: str | None = None

    @property
    def is_admin(self) -> bool:
        # Session token v2 carries "admin"; v1 carries "org:admin".
        return self.org_role in ("admin", "org:admin")


class JWKSCache:
    """Caches JWKS public keys.

    Before the first successful load, fetch attempts are retried at most every 5 s and a failure
    surfaces as 503 `auth_unavailable`. After a successful load, refetching for an unknown `kid`
    is throttled to once per 60 s. Loads are serialized so concurrent cold requests share one
    fetch.
    """

    def __init__(
        self,
        fetch: Callable[[], Awaitable[dict[str, Any]]],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch = fetch
        self._clock = clock
        self._keys: dict[str, Any] = {}
        self._loaded = False
        self._last_attempt: float | None = None
        self._lock = asyncio.Lock()

    def _throttled(self, interval: float) -> bool:
        last = self._last_attempt
        return last is not None and self._clock() - last < interval

    async def _load(self) -> None:
        try:
            data = await self._fetch()
            if not isinstance(data, dict) or not isinstance(data.get("keys"), list):
                raise TypeError("malformed JWKS")
        except Exception as exc:
            log.warning("JWKS fetch failed", exc_info=True)
            raise ServiceUnavailable("Signing keys unavailable", "auth_unavailable") from exc
        keys: dict[str, Any] = {}
        for jwk in data["keys"]:
            if not isinstance(jwk, dict) or not isinstance(jwk.get("kid"), str):
                continue
            try:
                keys[jwk["kid"]] = jwt.PyJWK(jwk).key
            except (jwt.PyJWTError, ValueError, TypeError, KeyError):
                continue
        self._keys = keys
        self._loaded = True

    async def key_for(self, kid: str) -> Any:
        if kid in self._keys:
            return self._keys[kid]
        async with self._lock:
            if kid in self._keys:
                return self._keys[kid]
            if not self._loaded:
                if self._throttled(_INITIAL_RETRY_INTERVAL):
                    raise ServiceUnavailable("Signing keys unavailable", "auth_unavailable")
                self._last_attempt = self._clock()
                await self._load()
                self._last_attempt = None  # a fresh initial load leaves the refetch budget
                if kid in self._keys:
                    return self._keys[kid]
            if self._throttled(_REFETCH_INTERVAL):
                raise Unauthorized("Unknown signing key")
            self._last_attempt = self._clock()
            try:
                await self._load()
            except ServiceUnavailable:
                pass  # the previous keys stay usable; the unknown kid is simply rejected
            if kid in self._keys:
                return self._keys[kid]
            raise Unauthorized("Unknown signing key")


def http_jwks_fetcher(url: str) -> Callable[[], Awaitable[dict[str, Any]]]:
    async def fetch() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data

    return fetch


async def verify_user(
    token: str,
    *,
    jwks: JWKSCache,
    issuer: str,
    authorized_parties: list[str],
    leeway: int = 5,
) -> User:
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        if not isinstance(kid, str):
            raise Unauthorized("Invalid token")
        key = await jwks.key_for(kid)
        # Tokens carrying `aud` are rejected: no audience is configured.
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=issuer,
            leeway=leeway,
            options={"require": ["exp", "nbf", "iss", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise Unauthorized("Invalid token") from exc

    azp = claims.get("azp")
    if azp is not None and azp not in authorized_parties:
        raise Unauthorized("Invalid token")

    org = claims.get("o")
    if isinstance(org, dict):
        org_id, role = org.get("id"), org.get("rol")
    else:
        org_id, role = claims.get("org_id"), claims.get("org_role")
    sub = str(claims["sub"])
    name = claims.get("name")
    return User(
        user_id=sub,
        name=name if isinstance(name, str) and name else sub,
        org_id=org_id if isinstance(org_id, str) and org_id else None,
        org_role=role if isinstance(role, str) and role else None,
    )


async def verify_token(
    token: str,
    *,
    jwks: JWKSCache,
    issuer: str,
    authorized_parties: list[str],
    leeway: int = 5,
) -> Principal:
    user = await verify_user(
        token, jwks=jwks, issuer=issuer, authorized_parties=authorized_parties, leeway=leeway
    )
    if user.org_id is None:
        raise Forbidden("No active organization")
    return Principal(
        user_id=user.user_id, org_id=user.org_id, name=user.name, org_role=user.org_role
    )


def _bearer(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise Unauthorized("Missing or malformed Authorization header")
    return token.strip()


async def get_principal(request: Request) -> Principal:
    settings = request.app.state.settings
    return await verify_token(
        _bearer(request),
        jwks=request.app.state.jwks,
        issuer=settings.clerk_issuer,
        authorized_parties=settings.clerk_authorized_parties,
    )


async def get_user(request: Request) -> User:
    """Like get_principal, but an active organization is not required."""
    settings = request.app.state.settings
    return await verify_user(
        _bearer(request),
        jwks=request.app.state.jwks,
        issuer=settings.clerk_issuer,
        authorized_parties=settings.clerk_authorized_parties,
    )
