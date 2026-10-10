"""Test helpers for Clerk-style JWT auth (shared by unit and API tests)."""

import base64
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.auth import JWKSCache

TEST_ISSUER = "https://clerk.test"
TEST_PARTY = "http://localhost:3000"
TEST_KID = "test-key"

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _b64(n: int) -> str:
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def jwk_for(key: rsa.RSAPrivateKey, kid: str = TEST_KID) -> dict[str, Any]:
    numbers = key.public_key().public_numbers()
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": _b64(numbers.n),
        "e": _b64(numbers.e),
    }


TEST_JWKS: dict[str, Any] = {"keys": [jwk_for(_PRIVATE_KEY)]}


def make_token(
    sub: str = "user_1",
    org_id: str | None = "org_a",
    name: str | None = "Lan",
    org_format: str = "v2",
    kid: str = TEST_KID,
    key: rsa.RSAPrivateKey | None = None,
    algorithm: str = "RS256",
    **overrides: Any,
) -> str:
    """Build a signed token. org_format "v2" -> {"o": {"id", "rol"}}, "v1" -> "org_id".

    Pass claim=None in overrides to drop that claim; other overrides replace/add claims.
    """
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": sub,
        "iss": TEST_ISSUER,
        "azp": TEST_PARTY,
        "iat": now,
        "nbf": now - 5,
        "exp": now + 300,
    }
    if name is not None:
        claims["name"] = name
    if org_id is not None:
        if org_format == "v2":
            claims["o"] = {"id": org_id, "rol": "admin"}
        else:
            claims["org_id"] = org_id
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    if algorithm == "HS256":
        return jwt.encode(claims, "x" * 32, algorithm="HS256", headers={"kid": kid})
    if algorithm == "none":
        return jwt.encode(claims, None, algorithm="none", headers={"kid": kid})
    signing_key = key or _PRIVATE_KEY
    pem = signing_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": kid})


def make_jwks_cache() -> JWKSCache:
    async def fetch() -> dict[str, Any]:
        return TEST_JWKS

    return JWKSCache(fetch)
