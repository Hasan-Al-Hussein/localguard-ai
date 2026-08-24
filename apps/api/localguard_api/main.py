"""FastAPI application factory and lifespan wiring."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from celery import Celery  # type: ignore[import-untyped]
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .agent.api import workflow_router
from .agent.checkpoints import in_memory_checkpointer, postgres_checkpointer
from .agent.orchestrator import WorkflowOrchestrator
from .agent.persistence import WorkflowApprovalService, WorkflowRepository
from .auth import AuthService
from .config import Settings, get_settings
from .database import Database
from .dispatch import (
    CleanupProcessor,
    OutboxDispatcher,
    ReconciliationLoops,
    outbox_repository,
)
from .errors import AppError
from .evaluation_routes import evaluation_router
from .ingestion import PrivateUploadStore
from .middleware import RequestContextMiddleware, current_correlation_id
from .providers import build_providers
from .repositories import audit_repository
from .retrieval import HybridRetriever
from .routes import auth_router, protected_router, public_router
from .services import DocumentService, IngestionProcessor, QuestionService


def _configure_logging(settings: Settings) -> None:
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or get_settings()
    _configure_logging(configured)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(configured)
        redis = Redis.from_url(configured.redis_url, decode_responses=True)
        upload_store = PrivateUploadStore(configured.upload_root)
        upload_store.prepare()
        chat, embeddings, ollama = build_providers(configured, redis)
        celery = Celery(
            "localguard-api",
            broker=configured.celery_broker_url,
            backend=configured.celery_result_backend,
        )
        celery.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            task_ignore_result=True,
        )
        outbox_dispatcher = OutboxDispatcher(database, celery, configured)
        cleanup_processor = CleanupProcessor(database, upload_store, configured)
        reconciliation = ReconciliationLoops(outbox_dispatcher, cleanup_processor)
        app.state.settings = configured
        app.state.database = database
        app.state.redis = redis
        app.state.celery = celery
        app.state.outbox_dispatcher = outbox_dispatcher
        app.state.cleanup_processor = cleanup_processor
        app.state.upload_store = upload_store
        app.state.ollama_provider = ollama
        app.state.auth_service = AuthService(configured)
        app.state.document_service = DocumentService(configured, upload_store)
        retriever = HybridRetriever(configured, embeddings)
        app.state.question_service = QuestionService(configured, retriever, chat)
        app.state.ingestion_processor = IngestionProcessor(configured, upload_store, embeddings)
        workflow_repository = WorkflowRepository(configured)
        workflow_approval_service = WorkflowApprovalService(configured, workflow_repository)
        checkpoint_context = None
        if configured.app_env == "test":
            checkpointer = in_memory_checkpointer()
        else:
            checkpoint_context = postgres_checkpointer(configured)
            checkpointer = await checkpoint_context.__aenter__()
        app.state.workflow_repository = workflow_repository
        app.state.workflow_approval_service = workflow_approval_service
        app.state.workflow_orchestrator = WorkflowOrchestrator(
            settings=configured,
            database=database,
            retriever=retriever,
            chat=chat,
            checkpointer=checkpointer,
            repository=workflow_repository,
            approval_service=workflow_approval_service,
        )
        app.state.outbox_repository = outbox_repository
        app.state.audit_repository = audit_repository
        await database.ping()
        reconciliation.start()
        try:
            yield
        finally:
            await reconciliation.close()
            if checkpoint_context is not None:
                await checkpoint_context.__aexit__(None, None, None)
            if ollama is not None:
                await ollama.close()
            await redis.aclose()
            await database.close()

    docs = "/docs" if configured.docs_enabled else None
    app = FastAPI(
        title="LocalGuard AI",
        version="0.1.0",
        debug=False,
        docs_url=docs,
        redoc_url=None,
        openapi_url="/openapi.json" if configured.docs_enabled else None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[configured.app_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            configured.csrf_header_name,
            "Idempotency-Key",
            "X-Correlation-ID",
        ],
        expose_headers=["X-Correlation-ID"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(configured.allowed_hosts))
    app.add_middleware(RequestContextMiddleware)
    app.include_router(public_router)
    app.include_router(auth_router)
    app.include_router(protected_router)
    app.include_router(workflow_router)
    app.include_router(evaluation_router)

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", current_correlation_id())
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "correlation_id": correlation_id,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del exc
        correlation_id = getattr(request.state, "correlation_id", current_correlation_id())
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "The request did not match the required schema",
                    "correlation_id": correlation_id,
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", current_correlation_id())
        structlog.get_logger("localguard.api").exception(
            "unhandled_error",
            path=request.url.path,
            correlation_id=correlation_id,
            exception_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "The request could not be completed",
                    "correlation_id": correlation_id,
                }
            },
        )

    return app


app = create_app()
