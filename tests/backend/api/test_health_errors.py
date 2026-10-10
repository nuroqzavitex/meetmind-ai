import httpx
from fastapi.testclient import TestClient

from app.core.errors import NotFound
from app.main import create_app


def test_health_ok() -> None:
    r = TestClient(create_app()).get("/api/v1/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_unknown_route_uses_error_envelope() -> None:
    r = TestClient(create_app()).get("/api/v1/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_app_error_envelope() -> None:
    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise NotFound("Không tìm thấy cuộc họp")

    r = TestClient(app).get("/boom")
    assert r.status_code == 404
    assert r.json() == {"error": {"code": "not_found", "message": "Không tìm thấy cuộc họp"}}


async def test_unhandled_error_is_enveloped_with_cors_headers() -> None:
    app = create_app()

    @app.get("/explode")
    def explode() -> None:
        raise RuntimeError("kaboom")

    origin = app.state.settings.cors_origins[0]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/explode", headers={"Origin": origin})
    assert r.status_code == 500
    assert r.json() == {"error": {"code": "internal_error", "message": "Lỗi máy chủ"}}
    assert r.headers["access-control-allow-origin"] == origin
