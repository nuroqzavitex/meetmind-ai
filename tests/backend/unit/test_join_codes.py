import pytest
from tests.backend.auth_helpers import TEST_ISSUER, TEST_PARTY, make_jwks_cache, make_token

from app.core.auth import verify_token, verify_user
from app.services.join_requests import ALPHABET, new_code, normalize_code


def test_new_code_shape() -> None:
    for _ in range(50):
        code = new_code()
        assert code.startswith("MM-") and len(code) == 12
        assert all(c in ALPHABET for c in code[3:].replace("-", ""))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("MM-7K3Q-X9P2", "MM-7K3Q-X9P2"),
        ("mm-7k3q-x9p2", "MM-7K3Q-X9P2"),
        (" 7K3Q X9P2 ", "MM-7K3Q-X9P2"),
        ("7k3qx9p2", "MM-7K3Q-X9P2"),
        ("MM-0000-0000", None),  # 0 is not in the alphabet
        ("MM-7K3Q", None),
        ("", None),
    ],
)
def test_normalize_code(raw: str, expected: str | None) -> None:
    assert normalize_code(raw) == expected


async def _user(token: str):  # type: ignore[no-untyped-def]
    return await verify_user(
        token, jwks=make_jwks_cache(), issuer=TEST_ISSUER, authorized_parties=[TEST_PARTY]
    )


async def test_user_without_org_is_accepted() -> None:
    user = await _user(make_token(org_id=None))
    assert user.user_id == "user_1" and user.org_id is None and user.org_role is None


@pytest.mark.parametrize(
    ("kwargs", "admin"),
    [
        ({"role": "admin"}, True),
        ({"role": "member"}, False),
        ({"org_format": "v1", "org_role": "org:admin"}, True),
        ({"org_format": "v1", "org_role": "org:member"}, False),
        ({"org_format": "v1"}, False),
    ],
)
async def test_admin_role_from_token(kwargs: dict[str, str], admin: bool) -> None:
    principal = await verify_token(
        make_token(org_id="org_a", **kwargs),
        jwks=make_jwks_cache(),
        issuer=TEST_ISSUER,
        authorized_parties=[TEST_PARTY],
    )
    assert principal.is_admin is admin
