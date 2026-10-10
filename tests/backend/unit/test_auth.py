import asyncio
import time
from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from tests.backend.auth_helpers import (
    OTHER_PRIVATE_KEY,
    TEST_ISSUER,
    TEST_JWKS,
    TEST_PARTY,
    make_jwks_cache,
    make_token,
)

from app.core.auth import JWKSCache, Principal, get_principal, verify_token
from app.core.config import Settings
from app.core.errors import (
    Forbidden,
    ServiceUnavailable,
    Unauthorized,
    install_error_handlers,
)


async def _verify(token: str, jwks: JWKSCache | None = None) -> Principal:
    return await verify_token(
        token,
        jwks=jwks or make_jwks_cache(),
        issuer=TEST_ISSUER,
        authorized_parties=[TEST_PARTY],
    )


async def test_v2_org_claim() -> None:
    principal = await _verify(make_token(org_id="org_a"))
    assert principal.org_id == "org_a"
    assert principal.user_id == "user_1"


async def test_v1_org_claim() -> None:
    principal = await _verify(make_token(org_id="org_b", org_format="v1"))
    assert principal.org_id == "org_b"


async def test_name_claim_and_fallback() -> None:
    assert (await _verify(make_token(name="Lan"))).name == "Lan"
    assert (await _verify(make_token(sub="user_9", name=None))).name == "user_9"


async def test_no_org_is_forbidden() -> None:
    with pytest.raises(Forbidden):
        await _verify(make_token(org_id=None))


_now = int(time.time())


@pytest.mark.parametrize(
    "token",
    [
        make_token(exp=_now - 600),
        make_token(nbf=_now + 600),
        make_token(iss="https://other.test"),
        make_token(azp="http://evil.test"),
        make_token(algorithm="HS256"),
        make_token(key=OTHER_PRIVATE_KEY),
        "not-a-jwt",
        make_token(algorithm="none"),
        make_token(nbf=None),
        make_token(exp=None),
        make_token(sub=None),  # type: ignore[arg-type]
        make_token(aud="someone"),
    ],
    ids=["expired", "future-nbf", "wrong-iss", "bad-azp", "hs256", "wrong-key", "garbage", "alg-none", "no-nbf", "no-exp", "no-sub", "aud"],
)
async def test_rejected_tokens(token: str) -> None:
    with pytest.raises(Unauthorized):
        await _verify(token)


async def test_unknown_kid_triggers_one_refetch() -> None:
    calls = 0
    clock = [1000.0]

    async def fetch() -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"keys": []} if calls == 1 else TEST_JWKS

    cache = JWKSCache(fetch, clock=lambda: clock[0])
    principal = await _verify(make_token(), cache)
    assert principal.org_id == "org_a"
    assert calls == 2

    clock[0] += 10
    with pytest.raises(Unauthorized):
        await _verify(make_token(kid="unknown-kid"), cache)
    assert calls == 2

    clock[0] += 61
    with pytest.raises(Unauthorized):
        await _verify(make_token(kid="unknown-kid"), cache)
    assert calls == 3


def test_dependency_missing_header_401() -> None:
    settings = Settings(clerk_issuer=TEST_ISSUER, clerk_authorized_parties=[TEST_PARTY])
    app = FastAPI()
    app.state.settings = settings
    app.state.jwks = make_jwks_cache()
    install_error_handlers(app)

    @app.get("/me")
    async def me(p: Annotated[Principal, Depends(get_principal)]) -> dict[str, str]:
        return {"org": p.org_id}

    client = TestClient(app)
    r = client.get("/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
    r = client.get("/me", headers={"Authorization": "Basic abc"})
    assert r.status_code == 401
    r = client.get("/me", headers={"Authorization": f"Bearer {make_token(org_id=None)}"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "no_active_org"
    r = client.get("/me", headers={"Authorization": f"Bearer {make_token()}"})
    assert r.status_code == 200
    assert r.json() == {"org": "org_a"}


async def test_failing_fetcher_is_throttled() -> None:
    calls = 0

    async def fetch() -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise RuntimeError("down")

    clock = [1000.0]
    cache = JWKSCache(fetch, clock=lambda: clock[0])
    for _ in range(5):
        with pytest.raises(ServiceUnavailable) as exc_info:
            await cache.key_for("test-key")
        assert exc_info.value.status == 503 and exc_info.value.code == "auth_unavailable"
    assert calls == 1

    clock[0] += 5.1  # never-loaded backoff is 5 s
    with pytest.raises(ServiceUnavailable):
        await cache.key_for("test-key")
    assert calls == 2


async def test_failed_fetch_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    async def fetch() -> dict[str, Any]:
        raise RuntimeError("down")

    with caplog.at_level("WARNING"), pytest.raises(ServiceUnavailable):
        await JWKSCache(fetch).key_for("test-key")
    assert any(r.exc_info and "down" in str(r.exc_info[1]) for r in caplog.records)


async def test_recovers_after_initial_failure() -> None:
    calls = 0
    clock = [0.0]

    async def fetch() -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("cold start")
        return TEST_JWKS

    cache = JWKSCache(fetch, clock=lambda: clock[0])
    with pytest.raises(ServiceUnavailable):
        await cache.key_for("test-key")
    clock[0] += 5.1
    assert await cache.key_for("test-key") is not None


async def test_concurrent_cold_requests_share_one_fetch() -> None:
    calls = 0

    async def fetch() -> dict[str, Any]:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return TEST_JWKS

    cache = JWKSCache(fetch)
    keys = await asyncio.gather(*(cache.key_for("test-key") for _ in range(5)))
    assert calls == 1
    assert all(k is keys[0] for k in keys)


async def test_fetch_failure_after_load_keeps_old_keys() -> None:
    calls = 0
    clock = [0.0]

    async def fetch() -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls > 1:
            raise RuntimeError("down")
        return TEST_JWKS

    cache = JWKSCache(fetch, clock=lambda: clock[0])
    await cache.key_for("test-key")
    clock[0] += 100
    with pytest.raises(Unauthorized):
        await cache.key_for("other")
    assert calls == 2
    assert await cache.key_for("test-key") is not None


async def test_jwks_with_only_unusable_keys_is_unauthorized() -> None:
    async def fetch() -> Any:
        return {"keys": [1, {"kid": 5}, {"kid": "k"}]}

    with pytest.raises(Unauthorized):
        await JWKSCache(fetch).key_for("test-key")


@pytest.mark.parametrize("body", [[], "x", {"keys": "x"}])
async def test_malformed_jwks_is_unavailable(body: Any) -> None:
    async def fetch() -> Any:
        return body

    with pytest.raises(ServiceUnavailable):
        await JWKSCache(fetch).key_for("test-key")


async def test_non_string_name_falls_back_to_sub() -> None:
    assert (await _verify(make_token(sub="user_3", name={"x": 1}))).name == "user_3"  # type: ignore[arg-type]
