"""Phase 1 business services for documents, ingestion, questions, and dashboard."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .agent.persistence import expire_pending_proposals, workflow_execution_lock_key
from .config import Settings
from .dispatch import (
    CleanupRepository,
    OutboxRepository,
    cleanup_repository,
    outbox_repository,
)
from .errors import (
    AppError,
    ConflictError,
    NotFoundError,
    RetryableServiceUnavailableError,
    ServiceUnavailableError,
    UnsafeUploadError,
)
from .ingestion import (
    PrivateUploadStore,
    ValidatedUpload,
    build_chunks,
    parse_document,
)
from .middleware import current_correlation_id
from .models import (
    ActionProposal,
    Answer,
    AuditEvent,
    Chunk,
    Citation,
    Document,
    DocumentRevision,
    DocumentState,
    ExtractedFinding,
    JobState,
    ProposalState,
    QuestionJob,
    SourceAnchor,
    User,
    WorkflowRun,
    utc_now,
)
from .providers import (
    INSUFFICIENT_ANSWER,
    ChatProvider,
    EmbeddingProvider,
    Evidence,
    GeneratedAnswer,
    QAContextDecision,
    QAContextVerdict,
    assess_qa_context,
    marker_citation_spans,
)
from .repositories import (
    AuditRepository,
    DocumentRepository,
    QuestionRepository,
    audit_repository,
    document_repository,
    question_repository,
)
from .retrieval import HybridRetriever


@dataclass(frozen=True, slots=True)
class AcceptedDocument:
    document: Document
    revision: DocumentRevision
    duplicate: bool
    dispatch_event_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class _QuestionCitationSpan:
    chunk_id: str
    quote: str
    relative_start: int
    relative_end: int


def _normalize_generated_answer(generated: GeneratedAnswer) -> str:
    """Enforce safe answer text at the persistence boundary for every provider."""

    if generated.insufficient_evidence:
        if generated.cited_chunk_ids:
            raise ServiceUnavailableError(
                "model_citation_invalid", "An insufficient answer cannot contain citations"
            )
        return INSUFFICIENT_ANSWER
    answer = generated.answer.strip()
    if not answer or len(answer) > 8000:
        raise ServiceUnavailableError(
            "model_answer_invalid", "The local model returned an invalid answer"
        )
    return answer


def _validate_question_answer_citations(
    question: str,
    *,
    generated_ids: tuple[str, ...],
    insufficient: bool,
    model_evidence: list[Evidence],
    qa_decision: QAContextDecision,
) -> None:
    """Bind injected-provider citations to exactly the evidence delivered to the model."""

    model_evidence_by_id = {item.chunk_id: item for item in model_evidence}
    if len(set(generated_ids)) != len(generated_ids) or any(
        identifier not in model_evidence_by_id for identifier in generated_ids
    ):
        raise ServiceUnavailableError(
            "model_citation_invalid", "The local model cited evidence it was not given"
        )
    if insufficient and generated_ids:
        raise ServiceUnavailableError(
            "model_citation_invalid", "An insufficient answer cannot contain citations"
        )
    if insufficient:
        return
    if not generated_ids:
        raise ServiceUnavailableError(
            "model_citation_missing", "The local model omitted required citations"
        )
    if qa_decision.verdict is QAContextVerdict.SUPPORTED:
        expected_ids = {item.chunk_id for item in qa_decision.evidence}
        if set(generated_ids) != expected_ids:
            raise ServiceUnavailableError(
                "model_grounding_invalid",
                "The cited evidence does not match the complete compact support set",
            )
    else:
        for identifier in generated_ids:
            item_decision = assess_qa_context(
                question,
                [model_evidence_by_id[identifier]],
            )
            if item_decision.verdict is QAContextVerdict.CLEARLY_ABSENT:
                raise ServiceUnavailableError(
                    "model_grounding_invalid",
                    "Each cited evidence chunk must independently remain relevant",
                )
    cited_decision = assess_qa_context(
        question,
        (model_evidence_by_id[identifier] for identifier in generated_ids),
    )
    if cited_decision.verdict is QAContextVerdict.CLEARLY_ABSENT:
        raise ServiceUnavailableError(
            "model_grounding_invalid",
            "The cited evidence does not support the requested subject and answer type",
        )


def _question_citation_spans(
    question: str,
    *,
    generated_ids: tuple[str, ...],
    evidence: list[Evidence],
    qa_decision: QAContextDecision,
) -> list[_QuestionCitationSpan]:
    """Resolve persisted quotes from the exact marker scope already validated for generation."""

    evidence_by_id = {item.chunk_id: item for item in evidence}
    if qa_decision.verdict is QAContextVerdict.SUPPORTED:
        compact_by_id = {item.chunk_id: item for item in qa_decision.evidence}
        output: list[_QuestionCitationSpan] = []
        for chunk_id in generated_ids:
            item = evidence_by_id.get(chunk_id)
            compact = compact_by_id.get(chunk_id)
            if item is None or compact is None:
                raise ServiceUnavailableError(
                    "model_citation_invalid", "The cited evidence could not be resolved"
                )
            marker_ids = [
                marker_id
                for binding_chunk_id, marker_id in qa_decision.marker_bindings
                if binding_chunk_id == chunk_id
            ]
            if not marker_ids:
                exact = compact.content.strip()
                if not exact or len(exact) > 1200 or item.content.count(exact) != 1:
                    raise ServiceUnavailableError(
                        "model_grounding_invalid",
                        "The supported markerless citation did not resolve exactly once",
                    )
                start = item.content.index(exact)
                output.append(
                    _QuestionCitationSpan(
                        chunk_id=chunk_id,
                        quote=exact,
                        relative_start=start,
                        relative_end=start + len(exact),
                    )
                )
                continue
            try:
                spans = {
                    candidate_id: (quote, start, end)
                    for candidate_id, quote, start, end in marker_citation_spans(item.content)
                }
            except ValueError as exc:
                raise ServiceUnavailableError(
                    "model_grounding_invalid",
                    "The cited evidence has ambiguous marker identifiers",
                ) from exc
            for marker_id in marker_ids:
                selected = spans.get(marker_id)
                if selected is None:
                    raise ServiceUnavailableError(
                        "model_grounding_invalid",
                        "The supported citation marker did not resolve in its source chunk",
                    )
                quote, start, end = selected
                output.append(
                    _QuestionCitationSpan(
                        chunk_id=chunk_id,
                        quote=quote,
                        relative_start=start,
                        relative_end=end,
                    )
                )
        return output

    output = []
    for chunk_id in generated_ids:
        item = evidence_by_id.get(chunk_id)
        if item is None:
            raise ServiceUnavailableError(
                "model_citation_invalid", "The cited evidence could not be resolved"
            )
        try:
            candidate_spans = marker_citation_spans(item.content)
        except ValueError as exc:
            raise ServiceUnavailableError(
                "model_grounding_invalid",
                "The cited evidence has ambiguous marker identifiers",
            ) from exc
        if not candidate_spans:
            start = len(item.content) - len(item.content.lstrip())
            end = len(item.content.rstrip())
            if end <= start or end - start > 1200:
                raise ServiceUnavailableError(
                    "model_grounding_invalid",
                    "The markerless cited evidence is not a bounded exact quote",
                )
            output.append(
                _QuestionCitationSpan(
                    chunk_id=chunk_id,
                    quote=item.content[start:end],
                    relative_start=start,
                    relative_end=end,
                )
            )
            continue
        supported_candidates = []
        for marker_id, quote, start, end in candidate_spans:
            marker_decision = assess_qa_context(
                question,
                [
                    Evidence(
                        chunk_id=chunk_id,
                        document_title=item.document_title,
                        anchor_label=item.anchor_label,
                        content=quote,
                        source_id=item.source_id,
                        marker_ids=(marker_id,),
                    )
                ],
            )
            if marker_decision.verdict is not QAContextVerdict.CLEARLY_ABSENT:
                supported_candidates.append((quote, start, end))
        if len(supported_candidates) != 1:
            raise ServiceUnavailableError(
                "model_grounding_invalid",
                "The cited evidence does not resolve to one bounded relevant marker",
            )
        quote, start, end = supported_candidates[0]
        output.append(
            _QuestionCitationSpan(
                chunk_id=chunk_id,
                quote=quote,
                relative_start=start,
                relative_end=end,
            )
        )
    return output


class DocumentService:
    def __init__(
        self,
        settings: Settings,
        store: PrivateUploadStore,
        repository: DocumentRepository = document_repository,
        audits: AuditRepository = audit_repository,
        outbox: OutboxRepository = outbox_repository,
        cleanup: CleanupRepository = cleanup_repository,
    ) -> None:
        self.settings = settings
        self.store = store
        self.repository = repository
        self.audits = audits
        self.outbox = outbox
        self.cleanup = cleanup

    async def accept(
        self, db: AsyncSession, upload: ValidatedUpload, actor: User
    ) -> AcceptedDocument:
        correlation_id = current_correlation_id()
        await self.repository.lock_content_key(db, actor.id, upload.sha256)
        duplicate = await self.repository.find_content_duplicate(db, actor.id, upload.sha256)
        if duplicate is not None:
            event_id: uuid.UUID | None = None
            if duplicate[1].state == DocumentState.QUEUED:
                event = await self.outbox.add(
                    db,
                    topic="localguard.ingest_revision",
                    aggregate_type="document_revision",
                    aggregate_id=duplicate[1].id,
                    dedupe_key=f"ingest:{duplicate[1].id}",
                    args=[str(duplicate[1].id)],
                    origin_correlation_id=duplicate[1].origin_correlation_id,
                )
                event_id = event.id
            await self.audits.add(
                db,
                actor_id=actor.id,
                action="document.upload",
                resource_type="document",
                resource_id=duplicate[0].id,
                outcome="duplicate",
                correlation_id=correlation_id,
                detail={"revision_id": str(duplicate[1].id)},
            )
            await db.commit()
            return AcceptedDocument(duplicate[0], duplicate[1], True, event_id)

        storage_key = self.store.store(upload)
        try:
            document, revision = await self.repository.create_document_revision(
                db,
                title=upload.title,
                actor_id=actor.id,
                original_filename=upload.original_filename,
                media_type=upload.media_type,
                storage_key=storage_key,
                content_sha256=upload.sha256,
                byte_size=len(upload.content),
                origin_correlation_id=correlation_id,
            )
            event = await self.outbox.add(
                db,
                topic="localguard.ingest_revision",
                aggregate_type="document_revision",
                aggregate_id=revision.id,
                dedupe_key=f"ingest:{revision.id}",
                args=[str(revision.id)],
                origin_correlation_id=correlation_id,
            )
            await self.audits.add(
                db,
                actor_id=actor.id,
                action="document.upload",
                resource_type="document",
                resource_id=document.id,
                outcome="accepted",
                correlation_id=correlation_id,
                causation_id=str(event.id),
                detail={
                    "revision_id": str(revision.id),
                    "byte_size": len(upload.content),
                    "outbox_event_id": str(event.id),
                },
            )
            await db.commit()
        except BaseException:
            await db.rollback()
            self.store.delete(storage_key)
            raise
        return AcceptedDocument(document, revision, False, event.id)

    async def detail(
        self, db: AsyncSession, document_id: uuid.UUID
    ) -> tuple[Document, DocumentRevision | None, list[SourceAnchor]]:
        document = await self.repository.get(db, document_id)
        if document is None:
            raise NotFoundError("Document")
        revision = await self.repository.current_revision(db, document)
        anchors = await self.repository.anchors(db, revision.id) if revision else []
        return document, revision, anchors

    async def page(self, db: AsyncSession, document_id: uuid.UUID, page: int) -> SourceAnchor:
        document, revision, anchors = await self.detail(db, document_id)
        del document
        if revision is None or revision.media_type != "application/pdf":
            raise NotFoundError("PDF page")
        for anchor in anchors:
            if anchor.stable_key == f"page:{page}":
                return anchor
        raise NotFoundError("PDF page")

    async def revision_section(
        self,
        db: AsyncSession,
        *,
        document_id: uuid.UUID,
        revision_id: uuid.UUID,
        anchor_key: str,
        start_offset: int,
        end_offset: int,
    ) -> tuple[SourceAnchor, str]:
        anchor = await self.repository.anchor(
            db,
            document_id=document_id,
            revision_id=revision_id,
            stable_key=anchor_key,
        )
        if anchor is None:
            raise NotFoundError("Document revision section")
        if start_offset < 0 or end_offset <= start_offset or end_offset > len(anchor.text):
            raise NotFoundError("Citation range")
        return anchor, anchor.text[start_offset:end_offset]

    async def queue_reprocess(
        self, db: AsyncSession, document_id: uuid.UUID, actor: User
    ) -> tuple[DocumentRevision, uuid.UUID]:
        document = await self.repository.get(db, document_id)
        if document is None or document.current_revision_id is None:
            raise NotFoundError("Document")
        revision = await self.repository.get_revision(db, document.current_revision_id, lock=True)
        if revision is None:
            raise NotFoundError("Document revision")
        if revision.state == DocumentState.PROCESSING:
            raise ConflictError("document_processing", "Document ingestion is already running")
        revision.state = DocumentState.QUEUED
        document.state = DocumentState.QUEUED
        event = await self.outbox.add(
            db,
            topic="localguard.ingest_revision",
            aggregate_type="document_revision",
            aggregate_id=revision.id,
            dedupe_key=f"reprocess:{revision.id}:{revision.updated_at.isoformat()}",
            args=[str(revision.id)],
            origin_correlation_id=current_correlation_id(),
        )
        await self.audits.add(
            db,
            actor_id=actor.id,
            action="document.reprocess",
            resource_type="document",
            resource_id=document.id,
            outcome="queued",
            correlation_id=current_correlation_id(),
            causation_id=str(event.id),
            detail={"outbox_event_id": str(event.id)},
        )
        await db.flush()
        return revision, event.id

    async def soft_delete(self, db: AsyncSession, document_id: uuid.UUID, actor: User) -> None:
        document = await self.repository.get(db, document_id, lock=True)
        if document is None:
            raise NotFoundError("Document")
        await self._purge_workflow_checkpoints(db, document.id)
        storage_keys = await self.repository.storage_keys(db, document.id)
        await self.repository.purge_extraction(db, document.id)
        document.deleted_at = func.now()
        document.state = DocumentState.DELETED
        for storage_key in storage_keys:
            await self.cleanup.add(db, resource_key=storage_key, document_id=document.id)
        await self.audits.add(
            db,
            actor_id=actor.id,
            action="document.delete",
            resource_type="document",
            resource_id=document.id,
            outcome="cleanup_queued",
            correlation_id=current_correlation_id(),
            detail={"cleanup_count": len(storage_keys)},
        )
        await db.flush()

    async def _purge_workflow_checkpoints(self, db: AsyncSession, document_id: uuid.UUID) -> None:
        rows = await db.execute(select(WorkflowRun.id, WorkflowRun.document_ids))
        run_ids = sorted(
            (run_id for run_id, scope in rows if str(document_id) in scope),
            key=str,
        )
        for run_id in run_ids:
            await db.execute(
                select(func.pg_advisory_xact_lock(workflow_execution_lock_key(run_id)))
            )
        if not run_ids:
            return
        parameters = {"thread_ids": [str(run_id) for run_id in run_ids]}
        for table_name in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            await db.execute(
                text(
                    f"DELETE FROM {table_name} "  # noqa: S608 - fixed internal allowlist
                    "WHERE thread_id = ANY(CAST(:thread_ids AS text[]))"
                ),
                parameters,
            )


class IngestionProcessor:
    def __init__(
        self,
        settings: Settings,
        store: PrivateUploadStore,
        embeddings: EmbeddingProvider,
        repository: DocumentRepository = document_repository,
        audits: AuditRepository = audit_repository,
    ) -> None:
        self.settings = settings
        self.store = store
        self.embeddings = embeddings
        self.repository = repository
        self.audits = audits

    async def process(
        self,
        db: AsyncSession,
        revision_id: uuid.UUID,
        *,
        terminal_on_transient_failure: bool = True,
    ) -> bool:
        revision = await self.repository.get_revision(db, revision_id, lock=True)
        if revision is None:
            raise NotFoundError("Document revision")
        if revision.state in {
            DocumentState.READY,
            DocumentState.FAILED,
            DocumentState.DELETED,
        }:
            return False
        if (
            revision.state == DocumentState.PROCESSING
            and revision.updated_at > utc_now() - timedelta(minutes=15)
        ):
            return False
        revision.state = DocumentState.PROCESSING
        document = await db.get(Document, revision.document_id)
        if document is not None:
            document.state = DocumentState.PROCESSING
        worker_correlation_id = f"worker-{uuid.uuid4().hex}"
        await self.audits.add(
            db,
            actor_id=None,
            action="ingestion.process",
            resource_type="document_revision",
            resource_id=revision.id,
            outcome="started",
            correlation_id=worker_correlation_id,
            causation_id=revision.origin_correlation_id,
            detail={"origin_correlation_id": revision.origin_correlation_id},
        )
        await db.commit()

        try:
            content = self.store.read(revision.storage_key, self.settings.max_upload_bytes)
            if hashlib.sha256(content).hexdigest() != revision.content_sha256:
                raise UnsafeUploadError("stored_file_changed", "Stored file integrity check failed")
            extension = {
                "application/pdf": ".pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
                "text/plain": ".txt",
            }.get(revision.media_type)
            if extension is None:
                raise UnsafeUploadError("unsupported_file_type", "Stored media type is unsupported")
            upload = ValidatedUpload(
                original_filename=revision.original_filename,
                title="",
                extension=extension,
                media_type=revision.media_type,
                content=content,
                sha256=revision.content_sha256,
            )
            parsed = parse_document(upload, self.settings)
            drafts = build_chunks(revision.id, parsed)
            if not drafts:
                raise UnsafeUploadError("no_chunks", "No retrievable text chunks were created")
            vectors: list[list[float]] = []
            for start in range(0, len(drafts), 16):
                vectors.extend(
                    await self.embeddings.embed(
                        [draft.content for draft in drafts[start : start + 16]]
                    )
                )
            anchors = [
                SourceAnchor(
                    id=uuid.uuid4(),
                    revision_id=revision.id,
                    stable_key=item.stable_key,
                    kind=item.kind,
                    label=item.label,
                    ordinal=item.ordinal,
                    start_offset=item.start_offset,
                    end_offset=item.end_offset,
                    text=item.text,
                )
                for item in parsed
            ]
            anchor_by_key = {anchor.stable_key: anchor for anchor in anchors}
            chunks = [
                Chunk(
                    revision_id=revision.id,
                    anchor_id=anchor_by_key[draft.anchor_key].id,
                    stable_id=draft.stable_id,
                    ordinal=draft.ordinal,
                    start_offset=draft.start_offset,
                    end_offset=draft.end_offset,
                    content=draft.content,
                    content_sha256=draft.content_sha256,
                    embedding=vector,
                )
                for draft, vector in zip(drafts, vectors, strict=True)
            ]
            locked_document = await self.repository.get(
                db,
                revision.document_id,
                lock=True,
                include_deleted=True,
            )
            locked_revision = await self.repository.get_revision(db, revision_id, lock=True)
            if locked_revision is None:
                raise NotFoundError("Document revision")
            if (
                locked_document is None
                or locked_document.deleted_at is not None
                or locked_document.state == DocumentState.DELETED
                or locked_document.current_revision_id != locked_revision.id
                or locked_revision.state != DocumentState.PROCESSING
            ):
                await self.audits.add(
                    db,
                    actor_id=None,
                    action="ingestion.process",
                    resource_type="document_revision",
                    resource_id=revision.id,
                    outcome="cancelled",
                    correlation_id=worker_correlation_id,
                    causation_id=revision.origin_correlation_id,
                    detail={"reason": "document_lifecycle_changed"},
                )
                await db.commit()
                return False
            await self.repository.replace_extraction(
                db, locked_document, locked_revision, anchors, chunks
            )
            await self.audits.add(
                db,
                actor_id=None,
                action="ingestion.process",
                resource_type="document_revision",
                resource_id=revision.id,
                outcome="succeeded",
                correlation_id=worker_correlation_id,
                causation_id=revision.origin_correlation_id,
                detail={"anchor_count": len(anchors), "chunk_count": len(chunks)},
            )
            await db.commit()
            return True
        except Exception as exc:
            await db.rollback()
            failed_document = await self.repository.get(
                db,
                revision.document_id,
                lock=True,
                include_deleted=True,
            )
            failed = await self.repository.get_revision(db, revision_id, lock=True)
            if failed is not None:
                code = exc.code if isinstance(exc, AppError) else "ingestion_failed"
                detail = exc.message if isinstance(exc, AppError) else "Document ingestion failed"
                deleted = failed_document is not None and (
                    failed_document.deleted_at is not None
                    or failed_document.state == DocumentState.DELETED
                )
                retrying = (
                    isinstance(exc, RetryableServiceUnavailableError)
                    and not terminal_on_transient_failure
                    and not deleted
                )
                if retrying:
                    await self.repository.release_revision_for_retry(db, failed_document, failed)
                else:
                    await self.repository.mark_revision_failed(
                        db, failed_document, failed, code, detail
                    )
                await self.audits.add(
                    db,
                    actor_id=None,
                    action="ingestion.process",
                    resource_type="document_revision",
                    resource_id=revision_id,
                    outcome="cancelled" if deleted else "retrying" if retrying else "failed",
                    correlation_id=worker_correlation_id,
                    causation_id=failed.origin_correlation_id,
                    detail={"error_code": code},
                )
                await db.commit()
                if deleted:
                    return False
            raise


class QuestionService:
    prompt_version = "grounded-qa-v1"

    def __init__(
        self,
        settings: Settings,
        retriever: HybridRetriever,
        chat: ChatProvider,
        repository: QuestionRepository = question_repository,
        audits: AuditRepository = audit_repository,
        outbox: OutboxRepository = outbox_repository,
    ) -> None:
        self.settings = settings
        self.retriever = retriever
        self.chat = chat
        self.repository = repository
        self.audits = audits
        self.outbox = outbox

    async def create(
        self,
        db: AsyncSession,
        actor: User,
        question: str,
        document_ids: list[uuid.UUID],
        idempotency_key: str,
    ) -> tuple[QuestionJob, bool, uuid.UUID]:
        if not 8 <= len(idempotency_key) <= 128:
            raise AppError("invalid_idempotency_key", "Idempotency-Key must be 8-128 characters")
        normalized_document_ids = sorted(str(value) for value in document_ids)
        request_hash = hashlib.sha256(
            json.dumps(
                {"question": question, "document_ids": normalized_document_ids},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        correlation_id = current_correlation_id()
        job, created = await self.repository.create_or_get(
            db,
            actor_id=actor.id,
            question=question,
            document_ids=document_ids,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            origin_correlation_id=correlation_id,
        )
        if job.request_hash != request_hash:
            raise ConflictError(
                "idempotency_payload_mismatch",
                "Idempotency-Key was already used for a different question payload",
            )
        event = await self.outbox.add(
            db,
            topic="localguard.answer_question",
            aggregate_type="question_job",
            aggregate_id=job.id,
            dedupe_key=f"question:{job.id}",
            args=[str(job.id)],
            origin_correlation_id=job.origin_correlation_id,
        )
        await self.audits.add(
            db,
            actor_id=actor.id,
            action="question.request",
            resource_type="question_job",
            resource_id=job.id,
            outcome="queued" if created else "duplicate",
            correlation_id=correlation_id,
            causation_id=str(event.id),
            detail={"request_hash": request_hash, "outbox_event_id": str(event.id)},
        )
        return job, not created, event.id

    async def process(
        self,
        db: AsyncSession,
        job_id: uuid.UUID,
        *,
        terminal_on_transient_failure: bool = True,
    ) -> bool:
        job = await self.repository.claim(db, job_id)
        if job is None:
            return False
        worker_correlation_id = f"worker-{uuid.uuid4().hex}"
        await self.audits.add(
            db,
            actor_id=job.requested_by_id,
            action="question.process",
            resource_type="question_job",
            resource_id=job.id,
            outcome="started",
            correlation_id=worker_correlation_id,
            causation_id=job.origin_correlation_id,
            detail={"origin_correlation_id": job.origin_correlation_id},
        )
        await db.commit()
        try:
            document_ids = [uuid.UUID(value) for value in job.document_ids]
            retrieval = await self.retriever.search(db, job.question, document_ids)
            evidence = [
                Evidence(
                    chunk_id=item.chunk.stable_id,
                    document_title=item.chunk.revision.document.title,
                    anchor_label=item.chunk.anchor.label,
                    content=item.chunk.content,
                )
                for item in retrieval.chunks
            ]
            qa_decision = assess_qa_context(job.question, evidence)
            model_evidence: list[Evidence] = []
            if not retrieval.sufficient or qa_decision.verdict is QAContextVerdict.CLEARLY_ABSENT:
                generated_text = INSUFFICIENT_ANSWER
                generated_ids: tuple[str, ...] = ()
                insufficient = True
                generation_ms = 0.0
                model_name = self.chat.model_name
            else:
                generation_started = time.perf_counter()
                generation_evidence = (
                    list(qa_decision.evidence)
                    if qa_decision.verdict is QAContextVerdict.SUPPORTED
                    else evidence
                )
                model_evidence = generation_evidence[:3]
                generated = await self.chat.answer(job.question, model_evidence)
                generation_ms = (time.perf_counter() - generation_started) * 1000
                generated_text = _normalize_generated_answer(generated)
                generated_ids = generated.cited_chunk_ids
                insufficient = generated.insufficient_evidence
                model_name = self.chat.model_name

            retrieved_by_id = {item.chunk.stable_id: item.chunk for item in retrieval.chunks}
            _validate_question_answer_citations(
                job.question,
                generated_ids=generated_ids,
                insufficient=insufficient,
                model_evidence=model_evidence,
                qa_decision=qa_decision,
            )
            citation_spans = _question_citation_spans(
                job.question,
                generated_ids=generated_ids,
                evidence=evidence,
                qa_decision=qa_decision,
            )
            answer = Answer(
                id=uuid.uuid4(),
                question_job_id=job.id,
                text=generated_text,
                insufficient_evidence=insufficient,
                model_name=model_name,
                prompt_version=self.prompt_version,
                retrieval_ms=retrieval.elapsed_ms,
                generation_ms=generation_ms,
            )
            citations: list[Citation] = []
            for ordinal, span in enumerate(citation_spans, start=1):
                chunk = retrieved_by_id[span.chunk_id]
                citations.append(
                    Citation(
                        answer_id=answer.id,
                        chunk_id=chunk.id,
                        ordinal=ordinal,
                        quote=span.quote,
                        document_id=chunk.revision.document_id,
                        revision_id=chunk.revision_id,
                        anchor_key=chunk.anchor.stable_key,
                        anchor_label=chunk.anchor.label,
                        start_offset=chunk.start_offset + span.relative_start,
                        end_offset=chunk.start_offset + span.relative_end,
                    )
                )
            claimed = await db.get(QuestionJob, job.id, with_for_update=True)
            if claimed is None or claimed.state != JobState.RUNNING:
                raise ConflictError("question_job_state_changed", "Question job state changed")
            await self.repository.store_answer(db, claimed, answer, citations)
            await self.audits.add(
                db,
                actor_id=job.requested_by_id,
                action="question.process",
                resource_type="question_job",
                resource_id=job.id,
                outcome="succeeded",
                correlation_id=worker_correlation_id,
                causation_id=job.origin_correlation_id,
                detail={
                    "answer_id": str(answer.id),
                    "citation_count": len(citations),
                    "retrieval_ms": retrieval.elapsed_ms,
                    "generation_ms": generation_ms,
                },
            )
            await db.commit()
            return True
        except BaseException as exc:
            await db.rollback()
            failed = await db.get(QuestionJob, job_id, with_for_update=True)
            if failed is not None and failed.state != JobState.SUCCEEDED:
                code = exc.code if isinstance(exc, AppError) else "question_failed"
                detail = exc.message if isinstance(exc, AppError) else "Question processing failed"
                retrying = (
                    isinstance(exc, RetryableServiceUnavailableError)
                    and not terminal_on_transient_failure
                )
                if retrying:
                    await self.repository.release_for_retry(db, failed)
                else:
                    await self.repository.fail(db, failed, code, detail)
                await self.audits.add(
                    db,
                    actor_id=failed.requested_by_id,
                    action="question.process",
                    resource_type="question_job",
                    resource_id=failed.id,
                    outcome="retrying" if retrying else "failed",
                    correlation_id=worker_correlation_id,
                    causation_id=failed.origin_correlation_id,
                    detail={"error_code": code},
                )
                await db.commit()
            raise


async def overview(db: AsyncSession) -> dict[str, object]:
    await expire_pending_proposals(
        db,
        correlation_id=current_correlation_id(),
        actor_id=None,
    )
    await db.commit()
    documents_total = int(
        await db.scalar(
            select(func.count()).select_from(Document).where(Document.deleted_at.is_(None))
        )
        or 0
    )
    documents_ready = int(
        await db.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.deleted_at.is_(None), Document.state == DocumentState.READY)
        )
        or 0
    )
    documents_processing = int(
        await db.scalar(
            select(func.count())
            .select_from(Document)
            .where(
                Document.deleted_at.is_(None),
                Document.state.in_([DocumentState.QUEUED, DocumentState.PROCESSING]),
            )
        )
        or 0
    )
    questions_total = int(await db.scalar(select(func.count()).select_from(QuestionJob)) or 0)
    questions_failed = int(
        await db.scalar(
            select(func.count())
            .select_from(QuestionJob)
            .where(QuestionJob.state == JobState.FAILED)
        )
        or 0
    )
    recent_documents = list(
        (
            await db.scalars(
                select(Document)
                .where(Document.deleted_at.is_(None))
                .order_by(Document.updated_at.desc())
                .limit(5)
            )
        ).all()
    )
    pending_approvals = int(
        await db.scalar(
            select(func.count())
            .select_from(ActionProposal)
            .where(ActionProposal.state == ProposalState.PENDING)
        )
        or 0
    )
    extracted_deadlines = list(
        (
            await db.scalars(
                select(ExtractedFinding)
                .where(ExtractedFinding.due_date.is_not(None))
                .order_by(ExtractedFinding.due_date, ExtractedFinding.created_at.desc())
                .limit(8)
            )
        ).all()
    )
    recent_activity = list(
        (
            await db.scalars(select(AuditEvent).order_by(AuditEvent.occurred_at.desc()).limit(10))
        ).all()
    )
    return {
        "documents_total": documents_total,
        "documents_ready": documents_ready,
        "documents_processing": documents_processing,
        "questions_total": questions_total,
        "questions_failed": questions_failed,
        "recent_documents": recent_documents,
        "pending_approvals": pending_approvals,
        "extracted_deadlines": extracted_deadlines,
        "recent_activity": recent_activity,
        "evaluation_summary": None,
    }
