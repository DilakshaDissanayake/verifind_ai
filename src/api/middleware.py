"""Request-id + latency middleware (SSE-safe)."""

from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.types import ASGIApp, Receive, Scope, Send


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        req_id = headers.get(b"x-request-id", b"").decode() or uuid.uuid4().hex[:16]
        scope.setdefault("state", {})["request_id"] = req_id
        start = time.perf_counter()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                ms = int((time.perf_counter() - start) * 1000)
                extra = [
                    (b"x-request-id", req_id.encode()),
                    (b"x-latency-ms", str(ms).encode()),
                ]
                message = {
                    **message,
                    "headers": list(message.get("headers", [])) + extra,
                }
            await send(message)

        await self.app(scope, receive, send_wrapper)


def install_middleware(app: FastAPI) -> None:
    app.add_middleware(RequestContextMiddleware)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        req_id = getattr(request.state, "request_id", None)
        logger.exception(
            "Unhandled {} {} [req_id={}]", request.method, request.url.path, req_id
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": req_id},
        )
