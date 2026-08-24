"""Persistence adapters; business rules remain in services."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import cast

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, lazyload

from .models import (
    Answer,
    AuditEvent,
    Chunk,
    Citation,
    Document,
    DocumentRevision,
    DocumentState,
    JobState,
    LoginThrottle,
    QuestionJob,
    SessionToken,
    SourceAnchor,
    User,
)
from .security import fingerprint, utc_now


class AuthRepository:
    async def find_user(self, db: AsyncSession, username: str) -> User | None:
        return cast(User | None, await db.scalar(select(User).where(User.username == username)))

    async def get_session(self, db: AsyncSession, digest: bytes) -> SessionToken | None:
        return cast(
            SessionToken | None,
            await db.scalar(
                select(SessionToken)
                .options(joinedload(SessionToken.user))
                .where(SessionToken.token_hash == digest)
            ),
        )

    async def create_session(self, db: AsyncSession, session: SessionToken) -> SessionToken:
        db.add(session)
        await db.flush()
        return session

    async def revoke_session(self, db: AsyncSession, digest: bytes, now: datetime) -> bool:
        session = await db.scalar(
            select(SessionToken)
            .options(lazyload(SessionToken.user))
            .where(SessionToken.token_hash == digest)
            .with_for_update()
        )
        if session is None or session.revoked_at is not None:
            return False
        session.revoked_at = now
        await db.flush()
        return True

    async def login_is_blocked(self, db: AsyncSession, principal: str, now: datetime) -> bool:
        row = await db.get(LoginThrottle, fingerprint(principal))
        return bool(row and row.blocked_until and row.blocked_until > now)

    async def record_login_failure(
        self,
        db: AsyncSession,
        principal: str,
        *,
        now: datetime,
        window_seconds: int,
        max_failures: int,
    ) -> None:
        key = fingerprint(principal)
        await db.execute(
            pg_insert(LoginThrottle)
            .values(principal_hash=key, window_started_at=now, failures=0)
            .on_conflict_do_nothing(index_elements=[LoginThrottle.principal_hash])
        )
        row = await db.scalar(
            select(LoginThrottle).where(LoginThrottle.principal_hash == key).with_for_update()
        )
        if row is None:
            raise RuntimeError("login throttle upsert did not produce a row")
        window = timedelta(seconds=window_seconds)
        if now - row.window_started_at >= window:
            row.window_started_at = now
            row.failures = 0
            row.blocked_until = None
        row.failures += 1
        if row.failures >= max_failures:
            row.blocked_until = now + window
        await db.flush()

    async def clear_login_failures(self, db: AsyncSession, principal: str) -> None:
        await db.execute(
            delete(LoginThrottle).where(LoginThrottle.principal_hash == fingerprint(principal))
        )


class AuditRepository:
    async def add(
        self,
        db: AsyncSession,
        *,
        actor_id: uuid.UUID | None,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID | None,
        outcome: str,
        correlation_id: str,
        detail: dict[str, object] | None = None,
        causation_id: str | None = None,
        thread_id: uuid.UUID | None = None,
        dedupe_key: str | None = None,
    ) -> AuditEvent:
        if dedupe_key is not None:
            event_id = uuid.uuid4()
            await db.execute(
                pg_insert(AuditEvent)
                .values(
                    id=event_id,
                    occurred_at=utc_now(),
                    actor_id=actor_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    outcome=outcome,
                    correlation_id=correlation_id,
                    causation_id=causation_id,
                    thread_id=thread_id,
                    dedupe_key=dedupe_key,
                    detail=dict(detail or {}),
                )
                .on_conflict_do_nothing(index_elements=[AuditEvent.dedupe_key])
            )
            event = await db.scalar(select(AuditEvent).where(AuditEvent.dedupe_key == dedupe_key))
            if event is None:
                raise RuntimeError("audit upsert did not produce an event")
            return event
        event = AuditEvent(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            correlation_id=correlation_id,
            causation_id=causation_id,
            thread_id=thread_id,
            dedupe_key=None,
            detail=dict(detail or {}),
        )
        db.add(event)
        await db.flush()
        return event


class DocumentRepository:
    async def lock_content_key(
        self, db: AsyncSession, actor_id: uuid.UUID, content_sha256: str
    ) -> None:
        material = hashlib.sha256(actor_id.bytes + bytes.fromhex(content_sha256)).digest()[:8]
        advisory_key = int.from_bytes(material, "big", signed=True)
        await db.execute(select(func.pg_advisory_xact_lock(advisory_key)))

    async def list_documents(
        self, db: AsyncSession, *, offset: int, limit: int
    ) -> tuple[list[Document], int]:
        predicate = Document.deleted_at.is_(None)
        items = list(
            (
                await db.scalars(
                    select(Document)
                    .where(predicate)
                    .order_by(Document.updated_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )
        total = int(
            await db.scalar(select(func.count()).select_from(Document).where(predicate)) or 0
        )
        return items, total

    async def get(
        self,
        db: AsyncSession,
        document_id: uuid.UUID,
        *,
        lock: bool = False,
        include_deleted: bool = False,
    ) -> Document | None:
        statement = select(Document).where(Document.id == document_id)
        if not include_deleted:
            statement = statement.where(Document.deleted_at.is_(None))
        if lock:
            statement = statement.with_for_update(of=Document).execution_options(
                populate_existing=True
            )
        return cast(Document | None, await db.scalar(statement))

    async def get_revision(
        self, db: AsyncSession, revision_id: uuid.UUID, *, lock: bool = False
    ) -> DocumentRevision | None:
        statement = select(DocumentRevision).where(DocumentRevision.id == revision_id)
        if lock:
            statement = statement.with_for_update(of=DocumentRevision).execution_options(
                populate_existing=True
            )
        return cast(DocumentRevision | None, await db.scalar(statement))

    async def current_revision(
        self, db: AsyncSession, document: Document
    ) -> DocumentRevision | None:
        if document.current_revision_id is None:
            return None
        return await db.get(DocumentRevision, document.current_revision_id)

    async def anchors(self, db: AsyncSession, revision_id: uuid.UUID) -> list[SourceAnchor]:
        return list(
            (
                await db.scalars(
                    select(SourceAnchor)
                    .where(SourceAnchor.revision_id == revision_id)
                    .order_by(SourceAnchor.ordinal)
                )
            ).all()
        )

    async def anchor(
        self,
        db: AsyncSession,
        *,
        document_id: uuid.UUID,
        revision_id: uuid.UUID,
        stable_key: str,
    ) -> SourceAnchor | None:
        return cast(
            SourceAnchor | None,
            await db.scalar(
                select(SourceAnchor)
                .join(DocumentRevision, DocumentRevision.id == SourceAnchor.revision_id)
                .join(Document, Document.id == DocumentRevision.document_id)
                .where(
                    Document.id == document_id,
                    Document.deleted_at.is_(None),
                    DocumentRevision.id == revision_id,
                    SourceAnchor.stable_key == stable_key,
                )
            ),
        )

    async def create_document_revision(
        self,
        db: AsyncSession,
        *,
        title: str,
        actor_id: uuid.UUID,
        original_filename: str,
        media_type: str,
        storage_key: str,
        content_sha256: str,
        byte_size: int,
        origin_correlation_id: str,
    ) -> tuple[Document, DocumentRevision]:
        document = Document(
            title=title,
            created_by_id=actor_id,
            source_content_sha256=content_sha256,
        )
        db.add(document)
        await db.flush()
        revision = DocumentRevision(
            document_id=document.id,
            revision_number=1,
            original_filename=original_filename,
            media_type=media_type,
            storage_key=storage_key,
            content_sha256=content_sha256,
            byte_size=byte_size,
            origin_correlation_id=origin_correlation_id,
        )
        db.add(revision)
        await db.flush()
        document.current_revision_id = revision.id
        await db.flush()
        return document, revision

    async def find_content_duplicate(
        self, db: AsyncSession, actor_id: uuid.UUID, content_sha256: str
    ) -> tuple[Document, DocumentRevision] | None:
        row = (
            await db.execute(
                select(Document, DocumentRevision)
                .join(DocumentRevision, DocumentRevision.document_id == Document.id)
                .where(
                    Document.created_by_id == actor_id,
                    Document.deleted_at.is_(None),
                    DocumentRevision.content_sha256 == content_sha256,
                )
                .order_by(DocumentRevision.created_at.desc())
                .limit(1)
            )
        ).first()
        return (row[0], row[1]) if row else None

    async def storage_keys(self, db: AsyncSession, document_id: uuid.UUID) -> list[str]:
        return list(
            (
                await db.scalars(
                    select(DocumentRevision.storage_key).where(
                        DocumentRevision.document_id == document_id
                    )
                )
            ).all()
        )

    async def purge_extraction(self, db: AsyncSession, document_id: uuid.UUID) -> None:
        revision_ids = select(DocumentRevision.id).where(
            DocumentRevision.document_id == document_id
        )
        await db.execute(
            update(Citation).where(Citation.revision_id.in_(revision_ids)).values(chunk_id=None)
        )
        await db.execute(delete(Chunk).where(Chunk.revision_id.in_(revision_ids)))
        await db.execute(delete(SourceAnchor).where(SourceAnchor.revision_id.in_(revision_ids)))
        await db.execute(
            update(DocumentRevision)
            .where(DocumentRevision.document_id == document_id)
            .values(state=DocumentState.DELETED)
        )

    async def replace_extraction(
        self,
        db: AsyncSession,
        document: Document,
        revision: DocumentRevision,
        anchors: list[SourceAnchor],
        chunks: list[Chunk],
    ) -> None:
        if (
            document.id != revision.document_id
            or document.deleted_at is not None
            or document.state == DocumentState.DELETED
            or document.current_revision_id != revision.id
            or revision.state != DocumentState.PROCESSING
        ):
            raise RuntimeError("document lifecycle changed before extraction replacement")
        await db.execute(delete(Chunk).where(Chunk.revision_id == revision.id))
        await db.execute(delete(SourceAnchor).where(SourceAnchor.revision_id == revision.id))
        db.add_all(anchors)
        await db.flush()
        db.add_all(chunks)
        await db.flush()
        revision.state = DocumentState.READY
        revision.error_code = None
        revision.error_detail = None
        revision.anchor_count = len(anchors)
        revision.extracted_characters = sum(len(anchor.text) for anchor in anchors)
        document.state = DocumentState.READY

    async def mark_revision_failed(
        self,
        db: AsyncSession,
        document: Document | None,
        revision: DocumentRevision,
        code: str,
        detail: str,
    ) -> None:
        if document is not None and (
            document.deleted_at is not None or document.state == DocumentState.DELETED
        ):
            revision.state = DocumentState.DELETED
            await db.flush()
            return
        revision.state = DocumentState.FAILED
        revision.error_code = code[:80]
        revision.error_detail = detail[:500]
        if document is not None:
            document.state = DocumentState.FAILED
        await db.flush()

    async def release_revision_for_retry(
        self,
        db: AsyncSession,
        document: Document | None,
        revision: DocumentRevision,
    ) -> None:
        if document is not None and (
            document.deleted_at is not None or document.state == DocumentState.DELETED
        ):
            revision.state = DocumentState.DELETED
            await db.flush()
            return
        revision.state = DocumentState.QUEUED
        revision.error_code = None
        revision.error_detail = None
        if document is not None:
            document.state = DocumentState.QUEUED
        await db.flush()


class QuestionRepository:
    async def get_by_idempotency(
        self, db: AsyncSession, actor_id: uuid.UUID, key: str
    ) -> QuestionJob | None:
        return cast(
            QuestionJob | None,
            await db.scalar(
                select(QuestionJob).where(
                    QuestionJob.requested_by_id == actor_id,
                    QuestionJob.idempotency_key == key,
                )
            ),
        )

    async def create_or_get(
        self,
        db: AsyncSession,
        *,
        actor_id: uuid.UUID,
        question: str,
        document_ids: list[uuid.UUID],
        idempotency_key: str,
        request_hash: str,
        origin_correlation_id: str,
    ) -> tuple[QuestionJob, bool]:
        job_id = uuid.uuid4()
        inserted_id = await db.scalar(
            pg_insert(QuestionJob)
            .values(
                id=job_id,
                requested_by_id=actor_id,
                question=question,
                document_ids=[str(value) for value in document_ids],
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                origin_correlation_id=origin_correlation_id,
                state=JobState.QUEUED,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            .on_conflict_do_nothing(
                index_elements=[QuestionJob.requested_by_id, QuestionJob.idempotency_key]
            )
            .returning(QuestionJob.id)
        )
        resolved_id = inserted_id or job_id
        job = await db.get(QuestionJob, resolved_id)
        if job is None and inserted_id is None:
            job = await self.get_by_idempotency(db, actor_id, idempotency_key)
        if job is None:
            raise RuntimeError("question idempotency upsert did not produce a row")
        return job, inserted_id is not None

    async def get(
        self, db: AsyncSession, job_id: uuid.UUID, actor_id: uuid.UUID
    ) -> QuestionJob | None:
        return cast(
            QuestionJob | None,
            await db.scalar(
                select(QuestionJob).where(
                    QuestionJob.id == job_id,
                    QuestionJob.requested_by_id == actor_id,
                )
            ),
        )

    async def claim(self, db: AsyncSession, job_id: uuid.UUID) -> QuestionJob | None:
        job = await db.scalar(select(QuestionJob).where(QuestionJob.id == job_id).with_for_update())
        if job is None or job.state in {JobState.SUCCEEDED, JobState.FAILED}:
            return None
        if (
            job.state == JobState.RUNNING
            and job.started_at is not None
            and job.started_at > utc_now() - timedelta(minutes=15)
        ):
            return None
        job.state = JobState.RUNNING
        job.started_at = utc_now()
        job.error_code = None
        job.error_detail = None
        await db.flush()
        return job

    async def store_answer(
        self,
        db: AsyncSession,
        job: QuestionJob,
        answer: Answer,
        citations: list[Citation],
    ) -> None:
        db.add(answer)
        await db.flush()
        for citation in citations:
            citation.answer_id = answer.id
        db.add_all(citations)
        job.state = JobState.SUCCEEDED
        job.completed_at = utc_now()
        await db.flush()

    async def fail(self, db: AsyncSession, job: QuestionJob, code: str, detail: str) -> None:
        job.state = JobState.FAILED
        job.error_code = code[:80]
        job.error_detail = detail[:500]
        job.completed_at = utc_now()
        await db.flush()

    async def release_for_retry(self, db: AsyncSession, job: QuestionJob) -> None:
        job.state = JobState.QUEUED
        job.error_code = None
        job.error_detail = None
        job.started_at = None
        job.completed_at = None
        await db.flush()


auth_repository = AuthRepository()
audit_repository = AuditRepository()
document_repository = DocumentRepository()
question_repository = QuestionRepository()
