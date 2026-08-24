"""Real PostgreSQL reliability regressions for durable request processing."""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from celery import Celery
from localguard_api.agent.persistence import WorkflowRepository
from localguard_api.config import Settings
from localguard_api.database import Database
from localguard_api.dispatch import (
    CleanupProcessor,
    CleanupRepository,
    OutboxDispatcher,
    OutboxRepository,
)
from localguard_api.errors import RetryableServiceUnavailableError, ServiceUnavailableError
from localguard_api.ingestion import PrivateUploadStore, ValidatedUpload
from localguard_api.models import (
    AuditEvent,
    Chunk,
    CleanupEntry,
    CleanupState,
    Document,
    DocumentRevision,
    DocumentState,
    JobState,
    LoginThrottle,
    OutboxEvent,
    OutboxState,
    QuestionJob,
    Role,
    SourceAnchor,
    User,
    WorkflowRun,
    WorkflowState,
    utc_now,
)
from localguard_api.providers import DeterministicProvider, EmbeddingProvider
from localguard_api.repositories import (
    AuthRepository,
    DocumentRepository,
    QuestionRepository,
)
from localguard_api.retrieval import HybridRetriever
from localguard_api.security import fingerprint, hash_password
from localguard_api.services import (
    AcceptedDocument,
    DocumentService,
    IngestionProcessor,
    QuestionService,
)
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_INTEGRATION") != "1",
        reason="set RUN_DB_INTEGRATION=1 inside the local Compose network",
    ),
]


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        allow_test_providers=True,
        ai_provider="deterministic",
        embedding_provider="deterministic",
        upload_root=tmp_path / "uploads",
        allowed_hosts=("testserver",),
    )


async def _create_user(database: Database, role: Role = Role.REVIEWER) -> User:
    async with database.sessions() as db:
        user = User(
            username=f"reliability-{uuid.uuid4().hex}",
            display_name="Reliability Test",
            password_hash=hash_password("reliability integration password"),
            role=role,
        )
        db.add(user)
        await db.commit()
        return user


async def _create_failed_question_outbox(
    database: Database, actor: User
) -> tuple[QuestionJob, OutboxEvent]:
    now = utc_now()
    async with database.sessions() as db:
        job = QuestionJob(
            requested_by_id=actor.id,
            question="A terminal question aggregate",
            document_ids=[],
            idempotency_key=f"terminal-{uuid.uuid4().hex}",
            request_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            origin_correlation_id=f"terminal-{uuid.uuid4().hex}",
            state=JobState.FAILED,
            error_code="terminal_failure",
            error_detail="Terminal failure",
            completed_at=now,
        )
        db.add(job)
        await db.flush()
        event = OutboxEvent(
            topic="localguard.answer_question",
            aggregate_type="question_job",
            aggregate_id=job.id,
            dedupe_key=f"terminal-question:{job.id}",
            payload={"args": [str(job.id)]},
            origin_correlation_id=job.origin_correlation_id,
            state=OutboxState.DISPATCHED,
            attempts=1,
            next_attempt_at=now,
            dispatched_at=now,
            celery_task_id=str(uuid.uuid4()),
        )
        db.add(event)
        await db.commit()
        return job, event


@pytest.mark.asyncio
async def test_revision_lock_targets_revision_table_with_joined_document(tmp_path: Path) -> None:
    database = Database(_settings(tmp_path))
    actor = await _create_user(database)
    repository = DocumentRepository()
    try:
        async with database.sessions() as db:
            document, revision = await repository.create_document_revision(
                db,
                title="Lock regression",
                actor_id=actor.id,
                original_filename="lock.txt",
                media_type="text/plain",
                storage_key=f"{uuid.uuid4().hex}.txt",
                content_sha256=hashlib.sha256(b"lock").hexdigest(),
                byte_size=4,
                origin_correlation_id="lock-regression",
            )
            await db.commit()
        async with database.sessions() as db:
            locked = await repository.get_revision(db, revision.id, lock=True)
            assert locked is not None
            assert locked.document.id == document.id
            await db.rollback()
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_outbox_dispatch_failure_is_reconciled_without_losing_intent(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    aggregate_id = uuid.uuid4()
    event_id = uuid.uuid4()
    async with database.sessions() as db:
        db.add(
            OutboxEvent(
                id=event_id,
                topic="localguard.test",
                aggregate_type="test",
                aggregate_id=aggregate_id,
                dedupe_key=f"test:{event_id}",
                payload={"args": [str(aggregate_id)]},
                origin_correlation_id="outbox-regression",
            )
        )
        await db.commit()

    class FlakyCelery:
        attempts = 0

        def send_task(self, *_args: object, **kwargs: object) -> SimpleNamespace:
            self.attempts += 1
            if self.attempts == 1:
                raise ConnectionError("broker unavailable")
            return SimpleNamespace(id=kwargs["task_id"])

    celery = FlakyCelery()
    dispatcher = OutboxDispatcher(database, cast(Celery, celery), settings)
    try:
        assert await dispatcher.dispatch_one(event_id) is None
        async with database.sessions() as db:
            pending = await db.get(OutboxEvent, event_id)
            assert pending is not None
            assert pending.state == OutboxState.PENDING
            assert pending.attempts == 1
            assert pending.last_error == "ConnectionError"
            await db.execute(
                update(OutboxEvent)
                .where(OutboxEvent.id == event_id)
                .values(next_attempt_at=utc_now())
            )
            await db.commit()
        assert await dispatcher.dispatch_one(event_id) == str(event_id)
        async with database.sessions() as db:
            dispatched = await db.get(OutboxEvent, event_id)
            assert dispatched is not None
            assert dispatched.state == OutboxState.DISPATCHED
            assert dispatched.attempts == 2
            outcomes = list(
                await db.scalars(
                    select(AuditEvent.outcome).where(
                        AuditEvent.causation_id == str(event_id),
                        AuditEvent.action == "outbox.dispatch",
                    )
                )
            )
            assert outcomes == ["deferred", "dispatched"]
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_targeted_dispatch_commits_terminal_aggregate_ack(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    actor = await _create_user(database, Role.VIEWER)
    _job, event = await _create_failed_question_outbox(database, actor)

    class MustNotPublish:
        def send_task(self, *_args: object, **_kwargs: object) -> object:
            raise AssertionError("terminal outbox events must not be published")

    dispatcher = OutboxDispatcher(database, cast(Celery, MustNotPublish()), settings)
    try:
        assert await dispatcher.dispatch_one(event.id) is None
        async with database.sessions() as db:
            persisted = await db.get(OutboxEvent, event.id)
        assert persisted is not None and persisted.state == OutboxState.ACKNOWLEDGED
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_drain_dispatch_commits_terminal_aggregate_ack(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    actor = await _create_user(database, Role.VIEWER)
    _job, event = await _create_failed_question_outbox(database, actor)

    class TerminalOnlyRepository(OutboxRepository):
        async def claim_one(
            self,
            db: AsyncSession,
            *,
            claim_ttl_seconds: int,
            event_id: uuid.UUID | None = None,
        ) -> OutboxEvent | None:
            assert event_id is None
            return await super().claim_one(
                db,
                claim_ttl_seconds=claim_ttl_seconds,
                event_id=event.id,
            )

    class MustNotPublish:
        def send_task(self, *_args: object, **_kwargs: object) -> object:
            raise AssertionError("terminal outbox events must not be published")

    dispatcher = OutboxDispatcher(
        database,
        cast(Celery, MustNotPublish()),
        settings,
        repository=TerminalOnlyRepository(),
    )
    try:
        assert await dispatcher.dispatch_one() is None
        async with database.sessions() as db:
            persisted = await db.get(OutboxEvent, event.id)
        assert persisted is not None and persisted.state == OutboxState.ACKNOWLEDGED
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_transient_ingestion_stays_retryable_until_final_attempt(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    actor = await _create_user(database)
    store = PrivateUploadStore(settings.upload_root)
    documents = DocumentService(settings, store)
    outbox = OutboxRepository()

    class UnavailableEmbeddings:
        embedding_model_name = "unavailable-embeddings"

        async def embed(self, _texts: list[str]) -> list[list[float]]:
            raise RetryableServiceUnavailableError("embedding_unavailable", "Embedding unavailable")

    content = b"[LG-POL-997:L001] A transient embedding failure must remain retryable."
    upload = ValidatedUpload(
        original_filename="transient-ingestion.txt",
        title="Transient ingestion",
        extension=".txt",
        media_type="text/plain",
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
    )
    try:
        async with database.sessions() as db:
            accepted = await documents.accept(db, upload, actor)
        assert accepted.dispatch_event_id is not None
        event_id = accepted.dispatch_event_id
        async with database.sessions() as db:
            await outbox.mark_dispatched(
                db,
                event_id,
                str(event_id),
                delivery_timeout_seconds=settings.outbox_delivery_timeout_seconds,
            )
            await db.commit()

        processor = IngestionProcessor(
            settings,
            store,
            cast(EmbeddingProvider, UnavailableEmbeddings()),
        )
        async with database.sessions() as db:
            with pytest.raises(ServiceUnavailableError):
                await processor.process(
                    db,
                    accepted.revision.id,
                    terminal_on_transient_failure=False,
                )
        async with database.sessions() as db:
            document = await db.get(Document, accepted.document.id)
            revision = await db.get(DocumentRevision, accepted.revision.id)
            event = await db.get(OutboxEvent, event_id)
            acknowledged = await outbox.acknowledge_if_complete(db, event_id)
            retry_audit = await db.scalar(
                select(AuditEvent).where(
                    AuditEvent.resource_id == accepted.revision.id,
                    AuditEvent.action == "ingestion.process",
                    AuditEvent.outcome == "retrying",
                )
            )
            await db.commit()
        assert document is not None and document.state == DocumentState.QUEUED
        assert revision is not None and revision.state == DocumentState.QUEUED
        assert event is not None and event.state == OutboxState.DISPATCHED
        assert not acknowledged
        assert retry_audit is not None

        async with database.sessions() as db:
            with pytest.raises(ServiceUnavailableError):
                await processor.process(
                    db,
                    accepted.revision.id,
                    terminal_on_transient_failure=True,
                )
        async with database.sessions() as db:
            document = await db.get(Document, accepted.document.id)
            revision = await db.get(DocumentRevision, accepted.revision.id)
            assert await outbox.acknowledge_if_complete(db, event_id)
            await db.commit()
            event = await db.get(OutboxEvent, event_id)
        assert document is not None and document.state == DocumentState.FAILED
        assert revision is not None and revision.state == DocumentState.FAILED
        assert event is not None and event.state == OutboxState.ACKNOWLEDGED
        async with database.sessions() as db:
            assert not await processor.process(
                db,
                accepted.revision.id,
                terminal_on_transient_failure=False,
            )
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_transient_question_stays_retryable_until_final_attempt(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    actor = await _create_user(database, Role.VIEWER)
    outbox = OutboxRepository()

    class UnavailableRetriever:
        async def search(
            self,
            _db: object,
            _question: str,
            _document_ids: list[uuid.UUID],
        ) -> object:
            raise RetryableServiceUnavailableError("retrieval_unavailable", "Retrieval unavailable")

    service = QuestionService(
        settings,
        cast(HybridRetriever, UnavailableRetriever()),
        DeterministicProvider(),
    )
    try:
        async with database.sessions() as db:
            job, _duplicate, event_id = await service.create(
                db,
                actor,
                "What must remain durable across a transient failure?",
                [],
                f"question-retry-{uuid.uuid4().hex}",
            )
            await db.commit()
        async with database.sessions() as db:
            await outbox.mark_dispatched(
                db,
                event_id,
                str(event_id),
                delivery_timeout_seconds=settings.outbox_delivery_timeout_seconds,
            )
            await db.commit()

        async with database.sessions() as db:
            with pytest.raises(ServiceUnavailableError):
                await service.process(
                    db,
                    job.id,
                    terminal_on_transient_failure=False,
                )
        async with database.sessions() as db:
            persisted = await db.get(QuestionJob, job.id)
            event = await db.get(OutboxEvent, event_id)
            acknowledged = await outbox.acknowledge_if_complete(db, event_id)
            retry_audit = await db.scalar(
                select(AuditEvent).where(
                    AuditEvent.resource_id == job.id,
                    AuditEvent.action == "question.process",
                    AuditEvent.outcome == "retrying",
                )
            )
            await db.commit()
        assert persisted is not None and persisted.state == JobState.QUEUED
        assert persisted.started_at is None and persisted.completed_at is None
        assert event is not None and event.state == OutboxState.DISPATCHED
        assert not acknowledged
        assert retry_audit is not None

        async with database.sessions() as db:
            with pytest.raises(ServiceUnavailableError):
                await service.process(
                    db,
                    job.id,
                    terminal_on_transient_failure=True,
                )
        async with database.sessions() as db:
            persisted = await db.get(QuestionJob, job.id)
            assert await outbox.acknowledge_if_complete(db, event_id)
            await db.commit()
            event = await db.get(OutboxEvent, event_id)
        assert persisted is not None and persisted.state == JobState.FAILED
        assert persisted.completed_at is not None
        assert event is not None and event.state == OutboxState.ACKNOWLEDGED
        async with database.sessions() as db:
            assert not await service.process(
                db,
                job.id,
                terminal_on_transient_failure=False,
            )
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_permanent_question_model_failure_is_terminal_and_acknowledgeable(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    actor = await _create_user(database, Role.VIEWER)
    outbox = OutboxRepository()

    class InvalidModelRetriever:
        calls = 0

        async def search(
            self,
            _db: object,
            _question: str,
            _document_ids: list[uuid.UUID],
        ) -> object:
            self.calls += 1
            raise ServiceUnavailableError(
                "model_schema_invalid", "The local model returned invalid output"
            )

    retriever = InvalidModelRetriever()
    service = QuestionService(
        settings,
        cast(HybridRetriever, retriever),
        DeterministicProvider(),
    )
    try:
        async with database.sessions() as db:
            job, _duplicate, event_id = await service.create(
                db,
                actor,
                "What must fail permanently after invalid model output?",
                [],
                f"question-permanent-{uuid.uuid4().hex}",
            )
            await db.commit()
        async with database.sessions() as db:
            await outbox.mark_dispatched(
                db,
                event_id,
                str(event_id),
                delivery_timeout_seconds=settings.outbox_delivery_timeout_seconds,
            )
            await db.commit()

        async with database.sessions() as db:
            with pytest.raises(ServiceUnavailableError) as captured:
                await service.process(
                    db,
                    job.id,
                    terminal_on_transient_failure=False,
                )
        assert captured.value.code == "model_schema_invalid"
        assert retriever.calls == 1

        async with database.sessions() as db:
            persisted = await db.get(QuestionJob, job.id)
            acknowledged = await outbox.acknowledge_if_complete(db, event_id)
            failed_audit = await db.scalar(
                select(AuditEvent).where(
                    AuditEvent.resource_id == job.id,
                    AuditEvent.action == "question.process",
                    AuditEvent.outcome == "failed",
                )
            )
            await db.commit()
            event = await db.get(OutboxEvent, event_id)
        assert persisted is not None and persisted.state == JobState.FAILED
        assert persisted.error_code == "model_schema_invalid"
        assert acknowledged
        assert event is not None and event.state == OutboxState.ACKNOWLEDGED
        assert failed_audit is not None
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_question_idempotency_is_atomic_and_payload_bound(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    actor = await _create_user(database, Role.VIEWER)
    repository = QuestionRepository()
    key = f"atomic-{uuid.uuid4().hex}"
    request_hash = hashlib.sha256(b"same request").hexdigest()

    async def insert_once() -> tuple[uuid.UUID, bool]:
        async with database.sessions() as db:
            job, created = await repository.create_or_get(
                db,
                actor_id=actor.id,
                question="What is the same request?",
                document_ids=[],
                idempotency_key=key,
                request_hash=request_hash,
                origin_correlation_id="question-atomic",
            )
            await db.commit()
            return job.id, created

    try:
        results = await asyncio.gather(insert_once(), insert_once())
        assert len({item[0] for item in results}) == 1
        assert sum(item[1] for item in results) == 1

        provider = DeterministicProvider()
        service = QuestionService(
            settings,
            HybridRetriever(settings, provider),
            provider,
            repository=repository,
        )
        async with database.sessions() as db:
            with pytest.raises(Exception) as captured:
                await service.create(
                    db,
                    actor,
                    "A different payload reusing the same key",
                    [],
                    key,
                )
            assert getattr(captured.value, "code", None) == "idempotency_payload_mismatch"
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_upload_dedupe_is_atomic_and_audit_chain_survives_worker_processing(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    actor = await _create_user(database)
    store = PrivateUploadStore(settings.upload_root)
    provider = DeterministicProvider()
    service = DocumentService(settings, store)
    processor = IngestionProcessor(settings, store, provider)
    content = b"[LG-POL-999:L001] Records must be retained for seven years."
    upload = ValidatedUpload(
        original_filename="atomic-upload.txt",
        title="atomic-upload",
        extension=".txt",
        media_type="text/plain",
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
    )

    async def accept_once() -> tuple[uuid.UUID, uuid.UUID, bool]:
        async with database.sessions() as db:
            accepted = await service.accept(db, upload, actor)
            return accepted.document.id, accepted.revision.id, accepted.duplicate

    try:
        accepted = await asyncio.gather(accept_once(), accept_once())
        assert len({item[0] for item in accepted}) == 1
        assert len({item[1] for item in accepted}) == 1
        assert sorted(item[2] for item in accepted) == [False, True]
        revision_id = accepted[0][1]
        async with database.sessions() as db:
            assert await processor.process(db, revision_id)
        async with database.sessions() as db:
            revision = await db.get(DocumentRevision, revision_id)
            assert revision is not None
            assert revision.state == DocumentState.READY
            events = list(
                (
                    await db.scalars(
                        select(AuditEvent)
                        .where(AuditEvent.resource_id.in_([revision.document_id, revision.id]))
                        .order_by(AuditEvent.occurred_at)
                    )
                ).all()
            )
            upload_event = next(item for item in events if item.action == "document.upload")
            worker_events = [item for item in events if item.action == "ingestion.process"]
            assert upload_event.causation_id is not None
            assert {item.outcome for item in worker_events} == {"started", "succeeded"}
            assert all(
                item.causation_id == revision.origin_correlation_id for item in worker_events
            )
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_cleanup_failure_keeps_recoverable_ledger_and_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    actor = await _create_user(database)
    store = PrivateUploadStore(settings.upload_root)
    upload = ValidatedUpload(
        "cleanup.txt",
        "cleanup",
        ".txt",
        "text/plain",
        b"cleanup evidence",
        hashlib.sha256(b"cleanup evidence").hexdigest(),
    )
    storage_key = store.store(upload)
    document_id = uuid.uuid4()
    async with database.sessions() as db:
        db.add(
            Document(
                id=document_id,
                title="Cleanup ledger",
                created_by_id=actor.id,
                source_content_sha256=upload.sha256,
            )
        )
        await db.flush()
        entry = await CleanupRepository().add(db, resource_key=storage_key, document_id=document_id)
        await db.commit()
    original_delete = store.delete

    def fail_delete(_storage_key: str) -> None:
        raise OSError("filesystem unavailable")

    monkeypatch.setattr(store, "delete", fail_delete)
    processor = CleanupProcessor(database, store, settings)
    try:
        for _ in range(50):
            assert not await processor.process_one()
            async with database.sessions() as db:
                observed = await db.get(CleanupEntry, entry.id)
                assert observed is not None
                if observed.last_error == "OSError":
                    break
        else:
            pytest.fail("the cleanup processor did not claim the target ledger entry")
        assert store.read(storage_key, settings.max_upload_bytes) == upload.content
        async with database.sessions() as db:
            pending = await db.get(CleanupEntry, entry.id)
            assert pending is not None
            assert pending.state == CleanupState.PENDING
            assert pending.last_error == "OSError"
            await db.execute(
                update(CleanupEntry)
                .where(CleanupEntry.id == entry.id)
                .values(next_attempt_at=utc_now())
            )
            await db.commit()
        monkeypatch.setattr(store, "delete", original_delete)
        for _ in range(50):
            await processor.process_one()
            async with database.sessions() as db:
                succeeded = await db.get(CleanupEntry, entry.id)
                assert succeeded is not None
                if succeeded.state == CleanupState.SUCCEEDED:
                    break
        else:
            pytest.fail("the cleanup processor did not complete the target ledger entry")
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_login_throttle_concurrent_first_failures_do_not_race(tmp_path: Path) -> None:
    database = Database(_settings(tmp_path))
    repository = AuthRepository()
    principal = f"login-race-{uuid.uuid4().hex}"

    async def fail_once() -> None:
        async with database.sessions() as db:
            await repository.record_login_failure(
                db,
                principal,
                now=utc_now(),
                window_seconds=900,
                max_failures=5,
            )
            await db.commit()

    try:
        await asyncio.gather(fail_once(), fail_once())
        async with database.sessions() as db:
            throttle = await db.get(LoginThrottle, fingerprint(principal))
            assert throttle is not None
            assert throttle.failures == 2
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_historical_revision_section_survives_current_revision_change(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    actor = await _create_user(database)
    document_id = uuid.uuid4()
    old_revision_id = uuid.uuid4()
    new_revision_id = uuid.uuid4()
    old_text = "Old authoritative evidence remains citeable."
    try:
        async with database.sessions() as db:
            document = Document(
                id=document_id,
                title="Revision history",
                created_by_id=actor.id,
                source_content_sha256="a" * 64,
                state=DocumentState.READY,
            )
            db.add(document)
            await db.flush()
            old_revision = DocumentRevision(
                id=old_revision_id,
                document_id=document_id,
                revision_number=1,
                original_filename="history.txt",
                media_type="text/plain",
                storage_key=f"{uuid.uuid4().hex}.txt",
                content_sha256="a" * 64,
                byte_size=len(old_text),
                state=DocumentState.READY,
                origin_correlation_id="history-old",
            )
            new_revision = DocumentRevision(
                id=new_revision_id,
                document_id=document_id,
                revision_number=2,
                original_filename="history.txt",
                media_type="text/plain",
                storage_key=f"{uuid.uuid4().hex}.txt",
                content_sha256="b" * 64,
                byte_size=16,
                state=DocumentState.READY,
                origin_correlation_id="history-new",
            )
            db.add_all([old_revision, new_revision])
            await db.flush()
            document.current_revision_id = new_revision.id
            db.add(
                SourceAnchor(
                    revision_id=old_revision.id,
                    stable_key="lines:1-1",
                    kind="text_lines",
                    label="Lines 1-1",
                    ordinal=1,
                    start_offset=0,
                    end_offset=len(old_text),
                    text=old_text,
                )
            )
            await db.commit()
        service = DocumentService(settings, PrivateUploadStore(settings.upload_root))
        async with database.sessions() as db:
            anchor, excerpt = await service.revision_section(
                db,
                document_id=document_id,
                revision_id=old_revision_id,
                anchor_key="lines:1-1",
                start_offset=4,
                end_offset=17,
            )
            assert anchor.revision_id == old_revision_id
            assert excerpt == old_text[4:17]
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_dispatched_outbox_is_republished_after_unacknowledged_delivery(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    actor = await _create_user(database)
    repository = OutboxRepository()
    run_id = uuid.uuid4()
    event_id = uuid.uuid4()

    class AcceptingButLossyCelery:
        def __init__(self) -> None:
            self.task_ids: list[str] = []

        def send_task(self, *_args: object, **kwargs: object) -> SimpleNamespace:
            task_id = str(kwargs["task_id"])
            self.task_ids.append(task_id)
            return SimpleNamespace(id=task_id)

    celery = AcceptingButLossyCelery()
    dispatcher = OutboxDispatcher(database, cast(Celery, celery), settings, repository=repository)
    try:
        async with database.sessions() as db:
            db.add(
                WorkflowRun(
                    id=run_id,
                    requested_by_id=actor.id,
                    idempotency_key=f"lost-{uuid.uuid4().hex}",
                    question="Propose a durable workflow task",
                    document_ids=[],
                    request_hash="a" * 64,
                    origin_correlation_id="lost-after-publish",
                    state=WorkflowState.RUNNING,
                )
            )
            db.add(
                OutboxEvent(
                    id=event_id,
                    topic="localguard.run_workflow",
                    aggregate_type="workflow_run",
                    aggregate_id=run_id,
                    dedupe_key=f"lost:{event_id}",
                    payload={"args": [str(run_id)]},
                    origin_correlation_id="lost-after-publish",
                )
            )
            await db.commit()

        assert await dispatcher.dispatch_one(event_id) == str(event_id)
        async with database.sessions() as db:
            await db.execute(
                update(OutboxEvent)
                .where(OutboxEvent.id == event_id)
                .values(next_attempt_at=utc_now())
            )
            await db.commit()
        assert await dispatcher.dispatch_one(event_id) == str(event_id)
        assert celery.task_ids == [str(event_id), str(event_id)]

        async with database.sessions() as db:
            run = await db.get(WorkflowRun, run_id, with_for_update=True)
            assert run is not None
            run.state = WorkflowState.WAITING_APPROVAL
            assert await repository.acknowledge_if_complete(db, event_id)
            await db.commit()
        async with database.sessions() as db:
            acknowledged = await db.get(OutboxEvent, event_id)
            assert acknowledged is not None
            assert acknowledged.state == OutboxState.ACKNOWLEDGED
            assert acknowledged.attempts == 2
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_worker_ack_before_mark_dispatched_cannot_regress_delivery_state(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    actor = await _create_user(database)
    repository = OutboxRepository()
    run_id = uuid.uuid4()
    event_id = uuid.uuid4()
    try:
        async with database.sessions() as db:
            db.add(
                WorkflowRun(
                    id=run_id,
                    requested_by_id=actor.id,
                    idempotency_key=f"early-ack-{uuid.uuid4().hex}",
                    question="Finish before publisher bookkeeping",
                    document_ids=[],
                    request_hash="b" * 64,
                    origin_correlation_id="early-ack",
                    state=WorkflowState.WAITING_APPROVAL,
                )
            )
            db.add(
                OutboxEvent(
                    id=event_id,
                    topic="localguard.run_workflow",
                    aggregate_type="workflow_run",
                    aggregate_id=run_id,
                    dedupe_key=f"early-ack:{event_id}",
                    payload={"args": [str(run_id)]},
                    origin_correlation_id="early-ack",
                )
            )
            await db.commit()
        async with database.sessions() as db:
            assert await repository.acknowledge_if_complete(db, event_id)
            await db.commit()
        async with database.sessions() as db:
            await repository.mark_dispatched(
                db,
                event_id,
                str(event_id),
                delivery_timeout_seconds=settings.outbox_delivery_timeout_seconds,
            )
            await db.commit()
        async with database.sessions() as db:
            event = await db.get(OutboxEvent, event_id)
            assert event is not None
            assert event.state == OutboxState.ACKNOWLEDGED
            assert event.dispatched_at is None
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_delete_during_embedding_cannot_recreate_extraction(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    actor = await _create_user(database)
    store = PrivateUploadStore(settings.upload_root)
    service = DocumentService(settings, store)
    started = asyncio.Event()
    release = asyncio.Event()
    deterministic = DeterministicProvider()

    class BlockingEmbeddings:
        embedding_model_name = "blocking-test"

        async def embed(self, texts: list[str]) -> list[list[float]]:
            started.set()
            await release.wait()
            return await deterministic.embed(texts)

    content = b"[LG-POL-998:L001] Deletion wins over stale ingestion work."
    upload = ValidatedUpload(
        original_filename="delete-race.txt",
        title="delete-race",
        extension=".txt",
        media_type="text/plain",
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
    )
    accepted: AcceptedDocument | None = None
    try:
        async with database.sessions() as db:
            accepted = await service.accept(db, upload, actor)
        assert accepted is not None
        processor = IngestionProcessor(
            settings,
            store,
            cast(EmbeddingProvider, BlockingEmbeddings()),
        )

        async def process() -> bool:
            async with database.sessions() as db:
                return await processor.process(db, accepted.revision.id)

        processing = asyncio.create_task(process())
        await asyncio.wait_for(started.wait(), timeout=5)
        async with database.sessions() as db:
            await service.soft_delete(db, accepted.document.id, actor)
            await db.commit()
        release.set()
        assert not await asyncio.wait_for(processing, timeout=5)

        async with database.sessions() as db:
            document = await db.get(Document, accepted.document.id)
            revision = await db.get(DocumentRevision, accepted.revision.id)
            chunk_count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(Chunk)
                    .where(Chunk.revision_id == accepted.revision.id)
                )
                or 0
            )
            anchor_count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(SourceAnchor)
                    .where(SourceAnchor.revision_id == accepted.revision.id)
                )
                or 0
            )
            assert document is not None and document.state == DocumentState.DELETED
            assert document.deleted_at is not None
            assert revision is not None and revision.state == DocumentState.DELETED
            assert chunk_count == 0
            assert anchor_count == 0
    finally:
        release.set()
        await database.close()


@pytest.mark.asyncio
async def test_deleted_document_content_can_be_reuploaded_without_integrity_error(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    actor = await _create_user(database)
    store = PrivateUploadStore(settings.upload_root)
    service = DocumentService(settings, store)
    content = b"A safely re-uploadable private document."
    upload = ValidatedUpload(
        original_filename="reupload.txt",
        title="reupload",
        extension=".txt",
        media_type="text/plain",
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
    )
    try:
        async with database.sessions() as db:
            first = await service.accept(db, upload, actor)
        async with database.sessions() as db:
            await service.soft_delete(db, first.document.id, actor)
            await db.commit()
        async with database.sessions() as db:
            second = await service.accept(db, upload, actor)
        assert not second.duplicate
        assert second.document.id != first.document.id
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_workflow_idempotency_is_atomic_and_payload_bound(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    actor = await _create_user(database, Role.VIEWER)
    repository = WorkflowRepository(settings)
    key = f"workflow-{uuid.uuid4().hex}"

    async def create_once() -> tuple[uuid.UUID, bool]:
        async with database.sessions() as db:
            run, created = await repository.create_or_get_run(
                db,
                actor=actor,
                question="What is the durable workflow answer?",
                document_ids=[],
                correlation_id="workflow-idempotency",
                idempotency_key=key,
            )
            await db.commit()
            return run.id, created

    try:
        results = await asyncio.gather(create_once(), create_once())
        assert len({item[0] for item in results}) == 1
        assert sum(item[1] for item in results) == 1
        async with database.sessions() as db:
            with pytest.raises(Exception) as captured:
                await repository.create_or_get_run(
                    db,
                    actor=actor,
                    question="A different workflow payload",
                    document_ids=[],
                    correlation_id="workflow-idempotency",
                    idempotency_key=key,
                )
            assert getattr(captured.value, "code", None) == "idempotency_payload_mismatch"
    finally:
        await database.close()
