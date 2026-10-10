import pytest


def test_authorized_parties_from_comma_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", "http://a.test,http://b.test")
    from app.core.config import Settings

    assert Settings(_env_file=None).clerk_authorized_parties == ["http://a.test", "http://b.test"]


def test_ai_settings_mapping() -> None:
    from app.core.config import Settings

    s = Settings(_env_file=None, llm_model_arbitrate="m-arb", prompt_version="v9")
    ai = s.ai_settings()
    assert ai.model_for("arbitrate") == "m-arb" and ai.prompt_version == "v9"


def test_item_patch_normalisation() -> None:
    import pytest
    from pydantic import ValidationError

    from app.schemas.items import ItemAction, ItemPatch

    p = ItemPatch(content="  hi  ", owner="   ", requester=" Lan ")
    assert p.content == "hi" and p.owner is None and p.requester == "Lan"
    assert ItemPatch(owner=None).model_dump(exclude_unset=True) == {"owner": None}
    with pytest.raises(ValidationError):
        ItemPatch(content="   ")
    with pytest.raises(ValidationError):
        ItemAction(action="reject", reason="x" * 1001)


async def test_arq_queue_fails_fast_when_redis_down() -> None:
    import time

    import pytest

    from app.workers.queue import ArqQueue

    start = time.monotonic()
    with pytest.raises(Exception):  # noqa: B017
        queue = ArqQueue("redis://127.0.0.1:1")
        await queue.enqueue("analyze", org_id="o", meeting_id="m", job_id="j")
    assert time.monotonic() - start < 5
