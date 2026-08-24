"""Durable task dispatch and recoverable private-file cleanup."""

from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta
from typing import Any, cast

import structlog
from celery import Celery  # type: ignore[import-untyped]
from celery.exceptions import CeleryError  # type: ignore[import-untyped]
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings
from .database import Database
from .ingestion import PrivateUploadStore
from .models import (
    ActionProposal,
    ApprovalDecision,
    CleanupEntry,
    CleanupState,
    DocumentRevision,
    DocumentState,
    JobState,
    OutboxEvent,
    OutboxState,
    QuestionJob,
    WorkflowRun,
    WorkflowState,
    utc_now,
)
from .repositories import AuditRepository, audit_repository

_DISPATCH_ERRORS = (CeleryError, OSError, ConnectionError, TimeoutError)


class OutboxRepository:
    async def add(
        self,
        db: AsyncSession,
        *,
        topic: str,
        aggregate_type: str,
        aggregate_id: uuid.UUID,
        dedupe_key: str,
        args: list[str],
        origin_correlation_id: str,
    ) -> OutboxEvent:
        event_id = uuid.uuid4()
        now = utc_now()
        await db.execute(
            pg_insert(OutboxEvent)
            .values(
                id=event_id,
                topic=topic,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                dedupe_key=dedupe_key,
                payload={"args": args},
                origin_correlation_id=origin_correlation_id,
                state=OutboxState.PENDING,
                attempts=0,
                next_attempt_at=now,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=[OutboxEvent.dedupe_key])
        )
        event = await db.scalar(select(OutboxEvent).where(OutboxEvent.dedupe_key == dedupe_key))
        if event is None:
            raise RuntimeError("outbox upsert did not produce an event")
        return event

    async def claim_one(
        self, db: AsyncSession, *, claim_ttl_seconds: int, event_id: uuid.UUID | None = None
    ) -> OutboxEvent | None:
        now = utc_now()
        stale_before = now - timedelta(seconds=claim_ttl_seconds)
        while True:
            statement = (
                select(OutboxEvent)
                .where(
                    OutboxEvent.state.in_([OutboxState.PENDING, OutboxState.DISPATCHED]),
                    OutboxEvent.next_attempt_at <= now,
                    or_(
                        OutboxEvent.claimed_at.is_(None),
                        OutboxEvent.claimed_at < stale_before,
                    ),
                )
                .order_by(OutboxEvent.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if event_id is not None:
                statement = statement.where(OutboxEvent.id == event_id)
            event = cast(OutboxEvent | None, await db.scalar(statement))
            if event is None:
                return None
            if await self._aggregate_completed(db, event):
                self._acknowledge(event)
                await db.flush()
                if event_id is not None:
                    return None
                continue
            was_dispatched = event.state == OutboxState.DISPATCHED
            event.state = OutboxState.PENDING
            event.claimed_at = now
            event.attempts += 1
            event.last_error = "delivery_unacknowledged" if was_dispatched else None
            await db.flush()
            return event

    async def mark_dispatched(
        self,
        db: AsyncSession,
        event_id: uuid.UUID,
        celery_task_id: str,
        *,
        delivery_timeout_seconds: int,
    ) -> OutboxEvent | None:
        event = await db.get(OutboxEvent, event_id, with_for_update=True)
        if event is None:
            return None
        if event.state == OutboxState.ACKNOWLEDGED:
            return event
        event.state = OutboxState.DISPATCHED
        event.celery_task_id = celery_task_id[:80]
        event.dispatched_at = utc_now()
        event.next_attempt_at = event.dispatched_at + timedelta(seconds=delivery_timeout_seconds)
        event.claimed_at = None
        event.last_error = None
        await db.flush()
        return event

    async def acknowledge_if_complete(self, db: AsyncSession, event_id: uuid.UUID) -> bool:
        event = await db.get(OutboxEvent, event_id, with_for_update=True)
        if event is None:
            return False
        if event.state == OutboxState.ACKNOWLEDGED:
            return True
        if not await self._aggregate_completed(db, event):
            return False
        self._acknowledge(event)
        await db.flush()
        return True

    async def release_after_failure(
        self, db: AsyncSession, event_id: uuid.UUID, error_name: str
    ) -> None:
        event = await db.get(OutboxEvent, event_id, with_for_update=True)
        if event is None or event.state == OutboxState.ACKNOWLEDGED:
            return
        delay = min(300, 2 ** min(event.attempts, 8))
        event.claimed_at = None
        event.next_attempt_at = utc_now() + timedelta(seconds=delay)
        event.last_error = error_name[:300]
        await db.flush()

    @staticmethod
    def _acknowledge(event: OutboxEvent) -> None:
        event.state = OutboxState.ACKNOWLEDGED
        event.claimed_at = None
        event.last_error = None

    async def _aggregate_completed(self, db: AsyncSession, event: OutboxEvent) -> bool:
        if event.topic == "localguard.ingest_revision":
            revision = await db.get(DocumentRevision, event.aggregate_id)
            return revision is None or revision.state in {
                DocumentState.READY,
                DocumentState.FAILED,
                DocumentState.DELETED,
            }
        if event.topic == "localguard.answer_question":
            job = await db.get(QuestionJob, event.aggregate_id)
            return job is None or job.state in {JobState.SUCCEEDED, JobState.FAILED}
        if event.topic == "localguard.run_workflow":
            run = await db.get(WorkflowRun, event.aggregate_id)
            return run is None or run.state != WorkflowState.RUNNING
        if event.topic == "localguard.resume_workflow":
            raw_args = event.payload.get("args")
            if not isinstance(raw_args, list) or len(raw_args) != 1:
                return False
            try:
                decision_id = uuid.UUID(str(raw_args[0]))
            except ValueError:
                return False
            decision = await db.get(ApprovalDecision, decision_id)
            if decision is None:
                return False
            if decision.applied_at is not None:
                return True
            proposal = await db.get(ActionProposal, decision.proposal_id)
            if proposal is None:
                return True
            run = await db.get(WorkflowRun, proposal.workflow_run_id)
            return run is None or run.state in {
                WorkflowState.COMPLETED,
                WorkflowState.REJECTED,
                WorkflowState.FAILED,
            }
        return False


class CleanupRepository:
    async def add(
        self,
        db: AsyncSession,
        *,
        resource_key: str,
        document_id: uuid.UUID,
    ) -> CleanupEntry:
        entry_id = uuid.uuid4()
        now = utc_now()
        await db.execute(
            pg_insert(CleanupEntry)
            .values(
                id=entry_id,
                resource_type="upload_file",
                resource_key=resource_key,
                document_id=document_id,
                state=CleanupState.PENDING,
                attempts=0,
                next_attempt_at=now,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(
                index_elements=[CleanupEntry.resource_type, CleanupEntry.resource_key]
            )
        )
        entry = await db.scalar(
            select(CleanupEntry).where(
                CleanupEntry.resource_type == "upload_file",
                CleanupEntry.resource_key == resource_key,
            )
        )
        if entry is None:
            raise RuntimeError("cleanup upsert did not produce an entry")
        return entry

    async def claim_one(self, db: AsyncSession, *, claim_ttl_seconds: int) -> CleanupEntry | None:
        now = utc_now()
        stale_before = now - timedelta(seconds=claim_ttl_seconds)
        entry = cast(
            CleanupEntry | None,
            await db.scalar(
                select(CleanupEntry)
                .where(
                    CleanupEntry.state == CleanupState.PENDING,
                    CleanupEntry.next_attempt_at <= now,
                    or_(CleanupEntry.claimed_at.is_(None), CleanupEntry.claimed_at < stale_before),
                )
                .order_by(CleanupEntry.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            ),
        )
        if entry is None:
            return None
        entry.claimed_at = now
        entry.attempts += 1
        entry.last_error = None
        await db.flush()
        return entry

    async def succeed(self, db: AsyncSession, entry_id: uuid.UUID) -> None:
        entry = await db.get(CleanupEntry, entry_id, with_for_update=True)
        if entry is None:
            return
        entry.state = CleanupState.SUCCEEDED
        entry.completed_at = utc_now()
        entry.claimed_at = None
        await db.flush()

    async def fail(self, db: AsyncSession, entry_id: uuid.UUID, error_name: str) -> None:
        entry = await db.get(CleanupEntry, entry_id, with_for_update=True)
        if entry is None or entry.state == CleanupState.SUCCEEDED:
            return
        delay = min(300, 2 ** min(entry.attempts, 8))
        entry.claimed_at = None
        entry.next_attempt_at = utc_now() + timedelta(seconds=delay)
        entry.last_error = error_name[:300]
        await db.flush()


class OutboxDispatcher:
    def __init__(
        self,
        database: Database,
        celery: Celery,
        settings: Settings,
        repository: OutboxRepository | None = None,
        audits: AuditRepository = audit_repository,
    ) -> None:
        self.database = database
        self.celery = celery
        self.settings = settings
        self.repository = repository or outbox_repository
        self.audits = audits

    async def dispatch_one(self, event_id: uuid.UUID | None = None) -> str | None:
        async with self.database.sessions() as db:
            event = await self.repository.claim_one(
                db,
                claim_ttl_seconds=self.settings.outbox_claim_ttl_seconds,
                event_id=event_id,
            )
            if event is None:
                await db.commit()
                return None
            snapshot = _OutboxSnapshot.from_event(event)
            await db.commit()

        try:
            result = await asyncio.to_thread(
                self.celery.send_task,
                snapshot.topic,
                args=snapshot.args,
                task_id=str(snapshot.id),
            )
            task_id = str(result.id)
        except _DISPATCH_ERRORS as exc:
            async with self.database.sessions() as db:
                await self.repository.release_after_failure(db, snapshot.id, type(exc).__name__)
                await self.audits.add(
                    db,
                    actor_id=None,
                    action="outbox.dispatch",
                    resource_type=snapshot.aggregate_type,
                    resource_id=snapshot.aggregate_id,
                    outcome="deferred",
                    correlation_id=snapshot.origin_correlation_id,
                    causation_id=str(snapshot.id),
                    detail={"error_type": type(exc).__name__, "attempt": snapshot.attempts},
                )
                await db.commit()
            return None

        async with self.database.sessions() as db:
            await self.repository.mark_dispatched(
                db,
                snapshot.id,
                task_id,
                delivery_timeout_seconds=self.settings.outbox_delivery_timeout_seconds,
            )
            await self.audits.add(
                db,
                actor_id=None,
                action="outbox.dispatch",
                resource_type=snapshot.aggregate_type,
                resource_id=snapshot.aggregate_id,
                outcome="dispatched",
                correlation_id=snapshot.origin_correlation_id,
                causation_id=str(snapshot.id),
                detail={"task_id": task_id, "topic": snapshot.topic},
            )
            await db.commit()
        return task_id

    async def drain(self, *, limit: int = 20) -> int:
        dispatched = 0
        for _ in range(limit):
            task_id = await self.dispatch_one()
            if task_id is None:
                break
            dispatched += 1
        return dispatched


class CleanupProcessor:
    def __init__(
        self,
        database: Database,
        store: PrivateUploadStore,
        settings: Settings,
        repository: CleanupRepository | None = None,
    ) -> None:
        self.database = database
        self.store = store
        self.settings = settings
        self.repository = repository or cleanup_repository

    async def process_one(self) -> bool:
        async with self.database.sessions() as db:
            entry = await self.repository.claim_one(
                db, claim_ttl_seconds=self.settings.outbox_claim_ttl_seconds
            )
            if entry is None:
                return False
            entry_id = entry.id
            resource_key = entry.resource_key
            await db.commit()
        try:
            await asyncio.to_thread(self.store.delete, resource_key)
        except OSError as exc:
            async with self.database.sessions() as db:
                await self.repository.fail(db, entry_id, type(exc).__name__)
                await db.commit()
            return False
        async with self.database.sessions() as db:
            await self.repository.succeed(db, entry_id)
            await db.commit()
        return True

    async def drain(self, *, limit: int = 20) -> int:
        processed = 0
        for _ in range(limit):
            if not await self.process_one():
                break
            processed += 1
        return processed


class ReconciliationLoops:
    def __init__(self, dispatcher: OutboxDispatcher, cleanup: CleanupProcessor) -> None:
        self.dispatcher = dispatcher
        self.cleanup = cleanup
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._outbox_loop(), name="localguard-outbox-reconciler"),
            asyncio.create_task(self._cleanup_loop(), name="localguard-cleanup-reconciler"),
        ]

    async def close(self) -> None:
        self._stop.set()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _outbox_loop(self) -> None:
        await self._run_loop(self.dispatcher.drain, self.dispatcher.settings.outbox_poll_seconds)

    async def _cleanup_loop(self) -> None:
        await self._run_loop(self.cleanup.drain, self.cleanup.settings.cleanup_poll_seconds)

    async def _run_loop(self, operation: Any, interval: float) -> None:
        logger = structlog.get_logger("localguard.reconciler")
        while not self._stop.is_set():
            try:
                await operation()
            except Exception as exc:  # defensive process boundary; next poll retries durable state
                logger.exception("reconciliation_iteration_failed", error_type=type(exc).__name__)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except TimeoutError:
                continue


class _OutboxSnapshot:
    def __init__(
        self,
        *,
        id: uuid.UUID,
        topic: str,
        aggregate_type: str,
        aggregate_id: uuid.UUID,
        args: list[str],
        origin_correlation_id: str,
        attempts: int,
    ) -> None:
        self.id = id
        self.topic = topic
        self.aggregate_type = aggregate_type
        self.aggregate_id = aggregate_id
        self.args = args
        self.origin_correlation_id = origin_correlation_id
        self.attempts = attempts

    @classmethod
    def from_event(cls, event: OutboxEvent) -> _OutboxSnapshot:
        raw_args = event.payload.get("args")
        if not isinstance(raw_args, list) or any(not isinstance(value, str) for value in raw_args):
            raise RuntimeError("outbox payload is invalid")
        return cls(
            id=event.id,
            topic=event.topic,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            args=list(raw_args),
            origin_correlation_id=event.origin_correlation_id,
            attempts=event.attempts,
        )


outbox_repository = OutboxRepository()
cleanup_repository = CleanupRepository()
