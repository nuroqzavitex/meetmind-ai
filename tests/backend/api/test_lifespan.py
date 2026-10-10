from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.session import make_engine
from app.main import create_app


def test_shutdown_disposes_created_engine() -> None:
    app = create_app()
    engine = make_engine("postgresql+asyncpg://app:app@localhost:5432/meeting_test")
    with patch.object(AsyncEngine, "dispose", new_callable=AsyncMock) as dispose:
        with TestClient(app):
            app.state.engine = engine
        dispose.assert_awaited_once()


def test_shutdown_without_engine_is_noop() -> None:
    app = create_app()
    with TestClient(app):
        assert not hasattr(app.state, "engine")
