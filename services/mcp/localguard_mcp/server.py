"""Loopback Streamable HTTP entrypoint for LocalGuard MCP."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, cast

import uvicorn
from fastmcp import FastMCP
from localguard_api.agent.persistence import WorkflowRepository
from localguard_api.config import Settings, get_settings
from localguard_api.database import Database
from localguard_api.providers import EmbeddingProvider, OllamaProvider, build_providers
from localguard_api.retrieval import HybridRetriever
from redis.asyncio import Redis
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .auth import DatabaseTokenVerifier
from .tools import register_tools

_LOOPBACK_HOSTS = ["127.0.0.1", "localhost", "::1"]


class OriginGuardMiddleware:
    """Reject browser origins that are not explicitly configured."""

    def __init__(self, app: ASGIApp, *, allowed_origins: tuple[str, ...]) -> None:
        self.app = app
        self.allowed_origins = frozenset(value.rstrip("/") for value in allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            origin = _header(scope, b"origin")
            if origin is not None and origin.rstrip("/") not in self.allowed_origins:
                response = JSONResponse(
                    {"error": {"code": "origin_denied", "message": "Origin is not allowed"}},
                    status_code=403,
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def create_mcp_server(
    *,
    settings: Settings,
    database: Database,
    embeddings: EmbeddingProvider,
    lifespan: Callable[[FastMCP[Any]], AbstractAsyncContextManager[dict[str, Any] | None]]
    | None = None,
) -> FastMCP:
    server = FastMCP(
        "LocalGuard AI",
        instructions=(
            "Search and inspect local documents or create inert task proposals. "
            "This server cannot approve proposals or create workflow tasks."
        ),
        version="0.1.0",
        auth=DatabaseTokenVerifier(database),
        lifespan=lifespan,
        on_duplicate="error",
        mask_error_details=True,
        strict_input_validation=True,
    )
    register_tools(
        server,
        settings=settings,
        database=database,
        retriever=HybridRetriever(settings, embeddings),
        workflow_repository=WorkflowRepository(settings),
    )

    @server.custom_route("/health", methods=["GET"])
    async def health(request: object) -> JSONResponse:
        del request
        await database.ping()
        return JSONResponse({"status": "ok", "service": "localguard-mcp"})

    return server


settings = get_settings()
database = Database(settings)
redis = Redis.from_url(settings.redis_url, decode_responses=True)
_chat, embeddings, ollama = build_providers(settings, redis)


@asynccontextmanager
async def lifespan(server: FastMCP[Any]) -> AsyncIterator[dict[str, Any] | None]:
    del server
    await database.ping()
    try:
        yield {"database": database}
    finally:
        await _close_runtime(ollama)


async def _close_runtime(runtime: OllamaProvider | None) -> None:
    if runtime is not None:
        await runtime.close()
    await redis.aclose()
    await database.close()


mcp = create_mcp_server(
    settings=settings,
    database=database,
    embeddings=embeddings,
    lifespan=lifespan,
)


def create_mcp_http_app(server: FastMCP[Any], configured: Settings) -> ASGIApp:
    """Build strict loopback HTTP transport with explicit Host and Origin policy."""

    middleware = [
        Middleware(OriginGuardMiddleware, allowed_origins=configured.mcp_allowed_origins),
        Middleware(
            CORSMiddleware,
            allow_origins=list(configured.mcp_allowed_origins),
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "mcp-protocol-version",
                "mcp-session-id",
            ],
            expose_headers=["mcp-session-id"],
            allow_credentials=False,
        ),
    ]
    return server.http_app(
        path="/mcp",
        middleware=middleware,
        stateless_http=True,
        host_origin_protection=True,
        allowed_hosts=_LOOPBACK_HOSTS,
        allowed_origins=list(configured.mcp_allowed_origins),
    )


app = create_mcp_http_app(mcp, settings)


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return cast(bytes, value).decode("ascii", errors="ignore")
    return None


if __name__ == "__main__":
    uvicorn.run(app, host=settings.mcp_bind_host, port=settings.mcp_port, log_level="info")
