"""Application errors and the uniform error envelope."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger(__name__)

_STATUS_CODES = {
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "file_too_large",
    422: "validation_error",
}


class AppError(Exception):
    status: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class NotFound(AppError):
    status = 404
    code = "not_found"


class Conflict(AppError):
    status = 409

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message, code)


class Unprocessable(AppError):
    status = 422

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message, code)


class PayloadTooLarge(AppError):
    status = 413
    code = "file_too_large"


class ServiceUnavailable(AppError):
    status = 503

    def __init__(self, message: str, code: str = "queue_unavailable") -> None:
        super().__init__(message, code)


class Unauthorized(AppError):
    status = 401
    code = "unauthorized"


class Forbidden(AppError):
    status = 403
    code = "no_active_org"


def _envelope(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _envelope(exc.status, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        return _envelope(exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        parts = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        return _envelope(422, "validation_error", "; ".join(parts) or "Invalid request")


class CatchAllMiddleware:
    """Turn unhandled exceptions into the error envelope.

    Add it before CORSMiddleware so CORS wraps it and the 500 still carries CORS headers
    (Starlette's ServerErrorMiddleware sits outside every user middleware).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception:
            log.exception("unhandled error on %s %s", scope.get("method"), scope.get("path"))
            if started:
                raise
            response = _envelope(500, "internal_error", "Lỗi máy chủ")
            await response(scope, receive, send)
