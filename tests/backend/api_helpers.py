from tests.backend.auth_helpers import make_token

MAX_UPLOAD = 50_000


class FakeQueue:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, str]] = []

    async def enqueue(self, kind: str, *, org_id: str, meeting_id: str, job_id: str) -> None:
        self.calls.append((kind, org_id, meeting_id, job_id))


def auth(org: str | None = "org_a", user: str = "user_1", name: str = "Lan") -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub=user, org_id=org, name=name)}"}
