"""Correlation, request logging, and baseline response-hardening middleware."""

from __future__ import annotations

import contextvars
import re
import time
import uuid
from typing import cast

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="unbound"
)
_SAFE_CORRELATION_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def current_correlation_id() -> str:
    return correlation_id_var.get()


class RequestContextMiddleware:
    """Attach a bounded correlation ID and emit a redacted structured access event."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = structlog.get_logger("localguard.http")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        supplied = _header(scope, b"x-correlation-id")
        correlation_id = (
            supplied if supplied and _SAFE_CORRELATION_ID.fullmatch(supplied) else uuid.uuid4().hex
        )
        token = correlation_id_var.set(correlation_id)
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        started = time.perf_counter()
        status_code = 500

        async def send_with_headers(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = MutableHeaders(scope=message)
                headers["X-Correlation-ID"] = correlation_id
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                headers["Cache-Control"] = "no-store"
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        finally:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            self.logger.info(
                "request_complete",
                method=scope.get("method"),
                path=scope.get("path"),
                status_code=status_code,
                duration_ms=elapsed_ms,
                correlation_id=correlation_id,
            )
            correlation_id_var.reset(token)


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return cast(bytes, value).decode("ascii", errors="ignore")
    return None
