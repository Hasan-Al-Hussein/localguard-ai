"""Automated, auditable end-to-end demo runner for the configured local provider."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import UploadFile
from langgraph.checkpoint.base import BaseCheckpointSaver
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis
from sqlalchemy import func, or_, select
from starlette.datastructures import Headers

from .agent.checkpoints import in_memory_checkpointer, postgres_checkpointer
from .agent.orchestrator import WorkflowOrchestrator
from .agent.persistence import ProposalBinding, WorkflowApprovalService, WorkflowRepository
from .config import Settings
from .database import Database
from .ingestion import PrivateUploadStore, validate_upload
from .middleware import correlation_id_var
from .models import (
    Answer,
    AuditEvent,
    Citation,
    DecisionKind,
    OutboxEvent,
    Role,
    TaskPriority,
    User,
    WorkflowTask,
    utc_now,
)
from .providers import ChatProvider, EmbeddingProvider, build_providers
from .repositories import audit_repository
from .retrieval import HybridRetriever
from .services import DocumentService, IngestionProcessor, QuestionService

_DEMO_SOURCE_ID = "LG-POL-001"
_DEMO_FIXTURE = Path("fixtures/documents/clean/lg-pol-001-vendor-access.pdf")
_DEMO_MARKER = "LG-POL-001:L010"
_DEMO_DUE_AT = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
_DEMO_QUESTION = (
    "How long does the Service Desk have to disable a vendor account after it receives "
    "an offboarding notice?"
)
_DEMO_ACTION = (
    "An authorized sponsor's vendor offboarding notice was received at "
    "2026-09-01T09:00:00Z. Propose the required account-disable task; do not execute "
    "it without review."
)


class DemoModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DemoDocument(DemoModel):
    source_id: str
    document_id: uuid.UUID
    revision_id: uuid.UUID
    filename: str
    content_sha256: str
    duplicate: bool
    correlation_id: str
    ingestion_ms: float = Field(ge=0)


class DemoCitation(DemoModel):
    citation_id: uuid.UUID
    document_id: uuid.UUID
    revision_id: uuid.UUID
    anchor_key: str
    anchor_label: str
    start_offset: int
    end_offset: int
    quote: str


class DemoQuestion(DemoModel):
    question_job_id: uuid.UUID
    answer_id: uuid.UUID
    prompt: str
    answer: str
    model_name: str
    correlation_id: str
    citations: list[DemoCitation] = Field(min_length=1)
    retrieval_ms: float = Field(ge=0)
    generation_ms: float = Field(ge=0)
    total_ms: float = Field(ge=0)


class DemoApprovalWorkflow(DemoModel):
    workflow_run_id: uuid.UUID
    prompt: str
    answer: str
    cited_chunk_ids: list[str] = Field(min_length=1)
    cited_marker_ids: list[str]
    proposal_id: uuid.UUID
    approval_decision_id: uuid.UUID
    outbox_event_id: uuid.UUID
    task_id: uuid.UUID
    task_title: str
    task_assignee: str
    task_priority: TaskPriority
    task_due_at: datetime
    tasks_before_approval: int
    tasks_after_approval: int
    tasks_after_replay: int
    stage_latency_ms: dict[str, float]
    total_ms: float = Field(ge=0)
    correlation_id: str


class DemoAuditEvent(DemoModel):
    event_id: uuid.UUID
    action: str
    outcome: str
    correlation_id: str
    causation_id: str | None
    thread_id: uuid.UUID | None


class DemoAudit(DemoModel):
    event_ids: list[uuid.UUID] = Field(min_length=1)
    actions: list[str] = Field(min_length=1)
    events: list[DemoAuditEvent] = Field(min_length=1)


class DemoArtifact(DemoModel):
    schema_version: str = "1.0"
    status: str = "verified"
    proof_scope: Literal["in_process_domain"] = "in_process_domain"
    provider: str
    chat_model: str
    embedding_model: str
    started_at: datetime
    completed_at: datetime
    total_ms: float = Field(ge=0)
    document: DemoDocument
    question: DemoQuestion
    approval_workflow: DemoApprovalWorkflow
    audit: DemoAudit


async def run_demo(
    settings: Settings,
    *,
    repository_root: Path,
    artifact_path: Path | None = None,
    viewer_username: str = "demo-viewer",
    reviewer_username: str = "demo-reviewer",
) -> DemoArtifact:
    """Run the real backend path and atomically persist its verification evidence."""

    _root, fixture, output_path = _demo_paths(repository_root, artifact_path)
    started_at = utc_now()
    total_started = time.perf_counter()
    database = Database(settings)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    store = PrivateUploadStore(settings.upload_root)
    store.prepare()
    chat, embeddings, ollama = build_providers(settings, redis)
    try:
        viewer, reviewer = await _load_demo_actors(
            database,
            viewer_username=viewer_username,
            reviewer_username=reviewer_username,
        )
        document_result = await _ingest_demo_fixture(
            settings=settings,
            database=database,
            store=store,
            embeddings=embeddings,
            actor=reviewer,
            fixture=fixture,
        )
        retriever = HybridRetriever(settings, embeddings)
        question_result = await _ask_demo_question(
            settings=settings,
            database=database,
            retriever=retriever,
            chat=chat,
            actor=viewer,
            document_id=document_result.document_id,
        )
        repository = WorkflowRepository(settings)
        approvals = WorkflowApprovalService(settings, repository)
        async with _demo_checkpointer(settings) as checkpointer:
            orchestrator = WorkflowOrchestrator(
                settings=settings,
                database=database,
                retriever=retriever,
                chat=chat,
                checkpointer=checkpointer,
                repository=repository,
                approval_service=approvals,
            )
            workflow_result = await _run_approval_workflow(
                database=database,
                repository=repository,
                approvals=approvals,
                orchestrator=orchestrator,
                requester=viewer,
                reviewer=reviewer,
                document_id=document_result.document_id,
            )
        audit_result = await _collect_demo_audit(
            database,
            document=document_result,
            question=question_result,
            workflow=workflow_result,
        )
        artifact = DemoArtifact(
            provider=settings.ai_provider,
            chat_model=chat.model_name,
            embedding_model=embeddings.embedding_model_name,
            started_at=started_at,
            completed_at=utc_now(),
            total_ms=_elapsed_ms(total_started),
            document=document_result,
            question=question_result,
            approval_workflow=workflow_result,
            audit=audit_result,
        )
        _write_artifact(output_path, artifact)
        return artifact
    finally:
        if ollama is not None:
            await ollama.close()
        await redis.aclose()
        await database.close()


async def _load_demo_actors(
    database: Database, *, viewer_username: str, reviewer_username: str
) -> tuple[User, User]:
    async with database.sessions() as db:
        actors = list(
            (
                await db.scalars(
                    select(User).where(User.username.in_([viewer_username, reviewer_username]))
                )
            ).all()
        )
    by_username = {actor.username: actor for actor in actors}
    viewer = by_username.get(viewer_username)
    reviewer = by_username.get(reviewer_username)
    if viewer is None or viewer.role != Role.VIEWER or not viewer.is_active:
        raise RuntimeError("The configured demo viewer is missing or inactive")
    if (
        reviewer is None
        or reviewer.role not in {Role.REVIEWER, Role.ADMIN}
        or not reviewer.is_active
    ):
        raise RuntimeError("The configured demo reviewer is missing, inactive, or unauthorized")
    return viewer, reviewer


async def _ingest_demo_fixture(
    *,
    settings: Settings,
    database: Database,
    store: PrivateUploadStore,
    embeddings: EmbeddingProvider,
    actor: User,
    fixture: Path,
) -> DemoDocument:
    started = time.perf_counter()
    raw, actual_digest = await asyncio.to_thread(_verified_fixture_bytes, fixture)
    upload = UploadFile(
        file=io.BytesIO(raw),
        filename=fixture.name,
        headers=Headers({"content-type": "application/pdf"}),
    )
    correlation_id = f"demo-upload-{uuid.uuid4().hex}"
    token = correlation_id_var.set(correlation_id)
    try:
        validated = await validate_upload(upload, settings)
        service = DocumentService(settings, store)
        async with database.sessions() as db:
            accepted = await service.accept(db, validated, actor)
        if accepted.duplicate:
            raise RuntimeError("The verification demo requires a fresh fixture upload; use --reset")
        processor = IngestionProcessor(settings, store, embeddings)
        async with database.sessions() as db:
            await processor.process(db, accepted.revision.id)
    finally:
        correlation_id_var.reset(token)
        await upload.close()
    return DemoDocument(
        source_id=_DEMO_SOURCE_ID,
        document_id=accepted.document.id,
        revision_id=accepted.revision.id,
        filename=fixture.name,
        content_sha256=actual_digest,
        duplicate=accepted.duplicate,
        correlation_id=correlation_id,
        ingestion_ms=_elapsed_ms(started),
    )


async def _ask_demo_question(
    *,
    settings: Settings,
    database: Database,
    retriever: HybridRetriever,
    chat: ChatProvider,
    actor: User,
    document_id: uuid.UUID,
) -> DemoQuestion:
    started = time.perf_counter()
    service = QuestionService(settings, retriever, chat)
    correlation_id = f"demo-question-{uuid.uuid4().hex}"
    token = correlation_id_var.set(correlation_id)
    try:
        async with database.sessions() as db:
            job, _duplicate, _event_id = await service.create(
                db,
                actor,
                _DEMO_QUESTION,
                [document_id],
                f"demo-question-{uuid.uuid4().hex}",
            )
            await db.commit()
        async with database.sessions() as db:
            await service.process(db, job.id)
    finally:
        correlation_id_var.reset(token)
    async with database.sessions() as db:
        answer = await db.scalar(select(Answer).where(Answer.question_job_id == job.id))
        if answer is None or answer.insufficient_evidence:
            raise RuntimeError("The demo question did not produce a grounded answer")
        citations = list(
            (
                await db.scalars(
                    select(Citation)
                    .where(Citation.answer_id == answer.id)
                    .order_by(Citation.ordinal)
                )
            ).all()
        )
    if not citations:
        raise RuntimeError("The demo answer did not persist a citation")
    if not _contains_one_hour(answer.text) or not any(
        _DEMO_MARKER in citation.quote and _contains_one_hour(citation.quote)
        for citation in citations
    ):
        raise RuntimeError("The demo answer did not prove the expected one-hour cited fact")
    return DemoQuestion(
        question_job_id=job.id,
        answer_id=answer.id,
        prompt=_DEMO_QUESTION,
        answer=answer.text,
        model_name=answer.model_name,
        correlation_id=correlation_id,
        citations=[
            DemoCitation(
                citation_id=item.id,
                document_id=item.document_id,
                revision_id=item.revision_id,
                anchor_key=item.anchor_key,
                anchor_label=item.anchor_label,
                start_offset=item.start_offset,
                end_offset=item.end_offset,
                quote=item.quote,
            )
            for item in citations
        ],
        retrieval_ms=answer.retrieval_ms,
        generation_ms=answer.generation_ms,
        total_ms=_elapsed_ms(started),
    )


async def _run_approval_workflow(
    *,
    database: Database,
    repository: WorkflowRepository,
    approvals: WorkflowApprovalService,
    orchestrator: WorkflowOrchestrator,
    requester: User,
    reviewer: User,
    document_id: uuid.UUID,
) -> DemoApprovalWorkflow:
    started = time.perf_counter()
    correlation_id = f"demo-workflow-{uuid.uuid4().hex}"
    token = correlation_id_var.set(correlation_id)
    try:
        async with database.sessions() as db:
            run = await repository.create_run(
                db,
                actor=requester,
                question=_DEMO_ACTION,
                document_ids=[document_id],
                correlation_id=correlation_id,
            )
            await audit_repository.add(
                db,
                actor_id=requester.id,
                action="workflow.request",
                resource_type="workflow_run",
                resource_id=run.id,
                outcome="started",
                correlation_id=correlation_id,
                thread_id=run.id,
                detail={"document_count": 1, "source": "demo_runner"},
            )
            await db.commit()
        state = await orchestrator.start(run.id)
        proposal_id_raw = state.get("proposal_id")
        if state.get("insufficient_evidence") or not proposal_id_raw:
            raise RuntimeError("The demo action did not produce an approval proposal")
        proposal_id = uuid.UUID(proposal_id_raw)
        async with database.sessions() as db:
            tasks_before = int(
                await db.scalar(
                    select(func.count())
                    .select_from(WorkflowTask)
                    .where(WorkflowTask.proposal_id == proposal_id)
                )
                or 0
            )
            proposal = await repository.get_proposal(db, proposal_id)
        if proposal is None or tasks_before != 0:
            raise RuntimeError("The approval interrupt did not preserve the zero-task invariant")
        async with database.sessions() as db:
            decision = await approvals.decide(
                db,
                proposal_id=proposal.id,
                actor=reviewer,
                decision=DecisionKind.APPROVE,
                binding=ProposalBinding(
                    version=proposal.version,
                    payload_hash=proposal.payload_hash,
                    evidence_snapshot_hash=proposal.evidence_snapshot_hash,
                    comment="Approved by the automated LocalGuard verification demo.",
                ),
                correlation_id=correlation_id,
            )
            await db.commit()
        resumed = await orchestrator.resume_decision(decision.decision.id)
        async with database.sessions() as db:
            tasks_after_approval = list(
                (
                    await db.scalars(
                        select(WorkflowTask).where(WorkflowTask.proposal_id == proposal.id)
                    )
                ).all()
            )
        await orchestrator.resume_decision(decision.decision.id)
        async with database.sessions() as db:
            tasks_after_replay = list(
                (
                    await db.scalars(
                        select(WorkflowTask).where(WorkflowTask.proposal_id == proposal.id)
                    )
                ).all()
            )
        if len(tasks_after_approval) != 1 or len(tasks_after_replay) != 1:
            raise RuntimeError("Approval and replay did not result in exactly one workflow task")
        task = tasks_after_replay[0]
        if (
            _DEMO_MARKER not in state.get("cited_marker_ids", [])
            or proposal.assignee is None
            or proposal.assignee.casefold() != "service desk"
            or proposal.priority != TaskPriority.HIGH
            or proposal.due_at != _DEMO_DUE_AT
            or task.assignee is None
            or task.assignee.casefold() != "service desk"
            or task.priority != TaskPriority.HIGH
            or task.due_at != _DEMO_DUE_AT
            or not _contains_one_hour(task.description)
        ):
            raise RuntimeError("The approved demo task did not preserve its bound payload/evidence")
        return DemoApprovalWorkflow(
            workflow_run_id=run.id,
            prompt=_DEMO_ACTION,
            answer=state.get("answer", ""),
            cited_chunk_ids=state.get("cited_chunk_ids", []),
            cited_marker_ids=state.get("cited_marker_ids", []),
            proposal_id=proposal.id,
            approval_decision_id=decision.decision.id,
            outbox_event_id=decision.outbox_event_id,
            task_id=task.id,
            task_title=task.title,
            task_assignee=task.assignee,
            task_priority=task.priority,
            task_due_at=task.due_at,
            tasks_before_approval=tasks_before,
            tasks_after_approval=len(tasks_after_approval),
            tasks_after_replay=len(tasks_after_replay),
            stage_latency_ms=resumed.get("stage_latency_ms", {}),
            total_ms=_elapsed_ms(started),
            correlation_id=correlation_id,
        )
    finally:
        correlation_id_var.reset(token)


async def _collect_demo_audit(
    database: Database,
    *,
    document: DemoDocument,
    question: DemoQuestion,
    workflow: DemoApprovalWorkflow,
) -> DemoAudit:
    resource_ids = {
        document.document_id,
        document.revision_id,
        question.question_job_id,
        workflow.workflow_run_id,
        workflow.proposal_id,
        workflow.approval_decision_id,
        workflow.task_id,
    }
    async with database.sessions() as db:
        events = list(
            (
                await db.scalars(
                    select(AuditEvent)
                    .where(
                        or_(
                            AuditEvent.resource_id.in_(resource_ids),
                            AuditEvent.thread_id == workflow.workflow_run_id,
                        )
                    )
                    .order_by(AuditEvent.occurred_at, AuditEvent.id)
                )
            ).all()
        )
        outbox_event = await db.get(OutboxEvent, workflow.outbox_event_id)
    if not events:
        raise RuntimeError("The demo did not persist its required audit evidence")
    if outbox_event is None or outbox_event.dedupe_key != (
        f"resume:{workflow.approval_decision_id}"
    ):
        raise RuntimeError("The demo approval decision is missing its durable resume intent")

    essential = [
        _require_audit_event(
            events,
            action="document.upload",
            outcome="accepted",
            correlation_id=document.correlation_id,
        ),
        _require_audit_event(
            events,
            action="ingestion.process",
            outcome="started",
            causation_id=document.correlation_id,
        ),
        _require_audit_event(
            events,
            action="ingestion.process",
            outcome="succeeded",
            causation_id=document.correlation_id,
        ),
        _require_audit_event(
            events,
            action="question.request",
            outcome="queued",
            correlation_id=question.correlation_id,
        ),
        _require_audit_event(
            events,
            action="question.process",
            outcome="started",
            causation_id=question.correlation_id,
        ),
        _require_audit_event(
            events,
            action="question.process",
            outcome="succeeded",
            causation_id=question.correlation_id,
        ),
        _require_audit_event(
            events,
            action="workflow.request",
            outcome="started",
            correlation_id=workflow.correlation_id,
            thread_id=workflow.workflow_run_id,
        ),
        _require_audit_event(
            events,
            action="workflow.analysis",
            outcome="grounded",
            correlation_id=workflow.correlation_id,
            thread_id=workflow.workflow_run_id,
        ),
        _require_audit_event(
            events,
            action="proposal.create",
            outcome="pending",
            correlation_id=workflow.correlation_id,
            thread_id=workflow.workflow_run_id,
        ),
        _require_audit_event(
            events,
            action="proposal.approve",
            outcome="approved",
            correlation_id=workflow.correlation_id,
            causation_id=str(workflow.approval_decision_id),
            thread_id=workflow.workflow_run_id,
        ),
        _require_audit_event(
            events,
            action="workflow.resume",
            outcome="started",
            correlation_id=workflow.correlation_id,
            causation_id=str(workflow.approval_decision_id),
            thread_id=workflow.workflow_run_id,
        ),
        _require_audit_event(
            events,
            action="workflow_task.create",
            outcome="succeeded",
            correlation_id=workflow.correlation_id,
            causation_id=str(workflow.approval_decision_id),
            thread_id=workflow.workflow_run_id,
        ),
        _require_audit_event(
            events,
            action="workflow.resume",
            outcome="applied",
            correlation_id=workflow.correlation_id,
            causation_id=str(workflow.approval_decision_id),
            thread_id=workflow.workflow_run_id,
        ),
    ]
    event_positions = {event.id: index for index, event in enumerate(events)}
    if [event_positions[event.id] for event in essential] != sorted(
        event_positions[event.id] for event in essential
    ):
        raise RuntimeError("The demo audit chain is not in the required causal order")
    upload_started, upload_succeeded = essential[1], essential[2]
    question_started, question_succeeded = essential[4], essential[5]
    if upload_started.correlation_id != upload_succeeded.correlation_id:
        raise RuntimeError("The ingestion audit transitions do not share a worker correlation")
    if question_started.correlation_id != question_succeeded.correlation_id:
        raise RuntimeError("The question audit transitions do not share a worker correlation")
    proposal_approval = essential[9]
    resume_started = essential[10]
    if proposal_approval.detail.get("outbox_event_id") != str(workflow.outbox_event_id):
        raise RuntimeError("The approval audit is not bound to its durable resume intent")
    if resume_started.detail.get("outbox_event_id") != str(workflow.outbox_event_id):
        raise RuntimeError("The resume audit is not bound to its durable outbox event")
    return DemoAudit(
        event_ids=[event.id for event in essential],
        actions=[event.action for event in essential],
        events=[
            DemoAuditEvent(
                event_id=event.id,
                action=event.action,
                outcome=event.outcome,
                correlation_id=event.correlation_id,
                causation_id=event.causation_id,
                thread_id=event.thread_id,
            )
            for event in essential
        ],
    )


def _require_audit_event(
    events: list[AuditEvent],
    *,
    action: str,
    outcome: str,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    thread_id: uuid.UUID | None = None,
) -> AuditEvent:
    matches = [
        event
        for event in events
        if event.action == action
        and event.outcome == outcome
        and (correlation_id is None or event.correlation_id == correlation_id)
        and (causation_id is None or event.causation_id == causation_id)
        and (thread_id is None or event.thread_id == thread_id)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one {action}/{outcome} audit event")
    return matches[0]


@asynccontextmanager
async def _demo_checkpointer(
    settings: Settings,
) -> AsyncIterator[BaseCheckpointSaver[Any]]:
    if settings.app_env == "test":
        yield in_memory_checkpointer()
        return
    async with postgres_checkpointer(settings) as checkpointer:
        yield checkpointer


def _manifest_digest(manifest_path: Path, source_id: str) -> str:
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents = raw.get("documents") if isinstance(raw, dict) else None
    if not isinstance(documents, list):
        raise RuntimeError("The LocalGuard fixture manifest is invalid")
    for document in documents:
        if isinstance(document, dict) and document.get("source_id") == source_id:
            digest = document.get("sha256")
            if isinstance(digest, str) and len(digest) == 64:
                return digest
    raise RuntimeError("The LocalGuard demo fixture is absent from its manifest")


def _demo_paths(repository_root: Path, artifact_path: Path | None) -> tuple[Path, Path, Path]:
    root = repository_root.resolve()
    fixture = (root / _DEMO_FIXTURE).resolve()
    if not fixture.is_relative_to(root) or not fixture.is_file():
        raise RuntimeError("The versioned LocalGuard demo fixture is unavailable")
    return root, fixture, artifact_path or root / "artifacts" / "verification" / "demo.json"


def _verified_fixture_bytes(fixture: Path) -> tuple[bytes, str]:
    raw = fixture.read_bytes()
    expected_digest = _manifest_digest(fixture.parents[1] / "manifest.json", _DEMO_SOURCE_ID)
    actual_digest = hashlib.sha256(raw).hexdigest()
    if actual_digest != expected_digest:
        raise RuntimeError("The LocalGuard demo fixture digest does not match its manifest")
    return raw, actual_digest


def _write_artifact(path: Path, artifact: DemoArtifact) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(artifact.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


def _contains_one_hour(value: str) -> bool:
    normalized = " ".join(value.casefold().split())
    return "one hour" in normalized or "1 hour" in normalized
