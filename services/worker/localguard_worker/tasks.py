"""Celery task adapters. Arguments are opaque IDs; PostgreSQL owns task state."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Protocol

from localguard_api.agent.checkpoints import postgres_checkpointer
from localguard_api.agent.orchestrator import WorkflowOrchestrator
from localguard_api.agent.persistence import WorkflowApprovalService, WorkflowRepository
from localguard_api.config import get_settings
from localguard_api.database import Database
from localguard_api.dispatch import outbox_repository
from localguard_api.errors import RetryableServiceUnavailableError
from localguard_api.ingestion import PrivateUploadStore
from localguard_api.providers import ChatProvider, EmbeddingProvider, build_providers
from localguard_api.retrieval import HybridRetriever
from localguard_api.services import IngestionProcessor, QuestionService
from redis.asyncio import Redis

from .app import celery_app


class _TaskRequest(Protocol):
    id: str | None
    retries: int


class _BoundTask(Protocol):
    request: _TaskRequest
    max_retries: int


async def _with_runtime(
    operation: Callable[[Database, ChatProvider, EmbeddingProvider], Awaitable[bool]],
    outbox_event_id: uuid.UUID | None,
) -> bool:
    settings = get_settings()
    database = Database(settings)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    chat, embeddings, ollama = build_providers(settings, redis)
    try:
        try:
            result = await operation(database, chat, embeddings)
        except Exception:
            await _acknowledge_terminal_safely(database, outbox_event_id)
            raise
        if outbox_event_id is not None:
            async with database.sessions() as db:
                await outbox_repository.acknowledge_if_complete(db, outbox_event_id)
                await db.commit()
        return result
    finally:
        if ollama is not None:
            await ollama.close()
        await redis.aclose()
        await database.close()


async def _acknowledge_terminal_safely(
    database: Database, outbox_event_id: uuid.UUID | None
) -> None:
    if outbox_event_id is None:
        return
    try:
        async with database.sessions() as db:
            await outbox_repository.acknowledge_if_complete(db, outbox_event_id)
            await db.commit()
    except Exception:
        # A stale DISPATCHED lease remains durable and will be reconciled.
        return


def _event_id(task: _BoundTask) -> uuid.UUID | None:
    if task.request.id is None:
        return None
    try:
        return uuid.UUID(task.request.id)
    except ValueError:
        return None


def _is_final_attempt(task: _BoundTask) -> bool:
    return task.request.retries >= task.max_retries


@celery_app.task(
    bind=True,
    name="localguard.ingest_revision",
    autoretry_for=(RetryableServiceUnavailableError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)  # type: ignore[untyped-decorator]
def ingest_revision(self: _BoundTask, revision_id: str) -> bool:
    parsed_id = uuid.UUID(revision_id)

    async def run(database: Database, chat: ChatProvider, embeddings: EmbeddingProvider) -> bool:
        del chat
        settings = get_settings()
        processor = IngestionProcessor(
            settings, PrivateUploadStore(settings.upload_root), embeddings
        )
        async with database.sessions() as session:
            return await processor.process(
                session,
                parsed_id,
                terminal_on_transient_failure=_is_final_attempt(self),
            )

    return asyncio.run(_with_runtime(run, _event_id(self)))


@celery_app.task(
    bind=True,
    name="localguard.answer_question",
    autoretry_for=(RetryableServiceUnavailableError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)  # type: ignore[untyped-decorator]
def answer_question(self: _BoundTask, question_job_id: str) -> bool:
    parsed_id = uuid.UUID(question_job_id)

    async def run(database: Database, chat: ChatProvider, embeddings: EmbeddingProvider) -> bool:
        settings = get_settings()
        retriever = HybridRetriever(settings, embeddings)
        service = QuestionService(settings, retriever, chat)
        async with database.sessions() as session:
            return await service.process(
                session,
                parsed_id,
                terminal_on_transient_failure=_is_final_attempt(self),
            )

    return asyncio.run(_with_runtime(run, _event_id(self)))


@celery_app.task(
    bind=True,
    name="localguard.run_workflow",
    autoretry_for=(RetryableServiceUnavailableError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)  # type: ignore[untyped-decorator]
def run_workflow(self: _BoundTask, workflow_run_id: str) -> bool:
    parsed_id = uuid.UUID(workflow_run_id)

    async def run(database: Database, chat: ChatProvider, embeddings: EmbeddingProvider) -> bool:
        settings = get_settings()
        repository = WorkflowRepository(settings)
        approvals = WorkflowApprovalService(settings, repository)
        async with postgres_checkpointer(settings) as checkpointer:
            orchestrator = WorkflowOrchestrator(
                settings=settings,
                database=database,
                retriever=HybridRetriever(settings, embeddings),
                chat=chat,
                checkpointer=checkpointer,
                repository=repository,
                approval_service=approvals,
            )
            await orchestrator.start(
                parsed_id, terminal_on_transient_failure=_is_final_attempt(self)
            )
        return True

    return asyncio.run(_with_runtime(run, _event_id(self)))


@celery_app.task(
    bind=True,
    name="localguard.resume_workflow",
    autoretry_for=(RetryableServiceUnavailableError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)  # type: ignore[untyped-decorator]
def resume_workflow(self: _BoundTask, approval_decision_id: str) -> bool:
    parsed_id = uuid.UUID(approval_decision_id)

    async def run(database: Database, chat: ChatProvider, embeddings: EmbeddingProvider) -> bool:
        settings = get_settings()
        repository = WorkflowRepository(settings)
        approvals = WorkflowApprovalService(settings, repository)
        async with postgres_checkpointer(settings) as checkpointer:
            orchestrator = WorkflowOrchestrator(
                settings=settings,
                database=database,
                retriever=HybridRetriever(settings, embeddings),
                chat=chat,
                checkpointer=checkpointer,
                repository=repository,
                approval_service=approvals,
            )
            await orchestrator.resume_decision(
                parsed_id, terminal_on_transient_failure=_is_final_attempt(self)
            )
        return True

    return asyncio.run(_with_runtime(run, _event_id(self)))
