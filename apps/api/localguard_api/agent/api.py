"""RBAC-enforced HTTP surface for workflows, approvals, tasks, findings, and audit."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_current_user, get_db, require_csrf, require_roles
from ..errors import AppError, AuthorizationError, NotFoundError
from ..middleware import current_correlation_id
from ..models import (
    ActionProposal,
    AuditEvent,
    Chunk,
    DecisionKind,
    Document,
    ExtractedFinding,
    FindingType,
    ProposalState,
    Role,
    TaskPriority,
    TaskState,
    User,
    WorkflowRun,
    WorkflowState,
    WorkflowTask,
)
from .persistence import (
    ProposalBinding,
    ProposalEditBinding,
    WorkflowApprovalService,
    WorkflowRepository,
    expire_pending_proposals,
)

workflow_router = APIRouter(dependencies=[Depends(get_current_user)])

DBSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CSRFUser = Annotated[User, Depends(require_csrf)]
ReviewerRead = Annotated[User, Depends(require_roles(Role.REVIEWER, Role.ADMIN))]
ReviewerWrite = Annotated[User, Depends(require_roles(Role.REVIEWER, Role.ADMIN, csrf=True))]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WorkflowRunRequest(StrictModel):
    question: str = Field(min_length=3, max_length=4000)
    document_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 3:
            raise ValueError("question is empty after normalization")
        return normalized


class WorkflowRunPublic(ORMModel):
    id: uuid.UUID
    requested_by_id: uuid.UUID
    question: str
    document_ids: list[str]
    state: WorkflowState
    intent: str | None
    answer_text: str | None
    insufficient_evidence: bool | None
    cited_chunk_ids: list[str]
    error_code: str | None
    error_detail: str | None
    created_at: datetime
    updated_at: datetime


class WorkflowStartAccepted(StrictModel):
    run: WorkflowRunPublic
    dispatch_job_id: str | None


class EvidenceReferencePublic(StrictModel):
    chunk_id: str
    available: bool
    document_id: uuid.UUID | None = None
    revision_id: uuid.UUID | None = None
    document_title: str | None = None
    anchor_key: str | None = None
    anchor_label: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    excerpt: str | None = None


class FindingPublic(ORMModel):
    id: uuid.UUID
    workflow_run_id: uuid.UUID
    finding_type: str
    summary: str
    normalized_value: str | None
    responsible_party: str | None
    due_date: date | None
    severity: str | None
    cited_chunk_ids: list[str]
    cited_marker_ids: list[str]
    fields: dict[str, str]
    origin: Literal["model", "deterministic_test_provider", "deterministic_evidence_normalizer"]
    normalizer_version: Literal["structured-obligation-binding-v2"] | None
    source_marker_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    derivation_reason: Literal["evidence_binding_confirmed"] | None
    evidence: list[EvidenceReferencePublic] = Field(default_factory=list)
    created_at: datetime

    @model_validator(mode="after")
    def validate_provenance(self) -> FindingPublic:
        provenance = (
            self.normalizer_version,
            self.source_marker_sha256,
            self.derivation_reason,
        )
        if self.origin == "deterministic_evidence_normalizer":
            if any(value is None for value in provenance):
                raise ValueError("deterministic finding provenance must be complete")
            if set(self.fields) != {"actor", "action", "deadline"} or any(
                not value.strip() for value in self.fields.values()
            ):
                raise ValueError("deterministic findings require exact structured fields")
            if not self.cited_marker_ids:
                raise ValueError("deterministic findings require exact source markers")
        elif any(value is not None for value in provenance):
            raise ValueError("provider findings cannot assert application provenance")
        return self


class FindingList(StrictModel):
    items: list[FindingPublic]
    total: int
    offset: int
    limit: int


class ProposalPublic(ORMModel):
    id: uuid.UUID
    workflow_run_id: uuid.UUID
    created_by_id: uuid.UUID
    previous_proposal_id: uuid.UUID | None
    version: int
    kind: str
    state: ProposalState
    title: str
    description: str
    assignee: str | None
    priority: TaskPriority
    due_at: datetime | None
    reasoning_summary: str
    cited_chunk_ids: list[str]
    evidence: list[EvidenceReferencePublic] = Field(default_factory=list)
    payload_hash: str
    evidence_snapshot_hash: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class ProposalList(StrictModel):
    items: list[ProposalPublic]
    total: int
    offset: int
    limit: int


class ApprovalRequest(ProposalBinding):
    pass


class RejectionRequest(ProposalBinding):
    pass


class EditRequest(ProposalEditBinding):
    pass


class DecisionPublic(ORMModel):
    id: uuid.UUID
    proposal_id: uuid.UUID
    proposal_version: int
    decided_by_id: uuid.UUID
    decision: DecisionKind
    payload_hash: str
    evidence_snapshot_hash: str
    comment: str | None
    replacement_proposal_id: uuid.UUID | None
    decided_at: datetime
    applied_at: datetime | None


class WorkflowTaskPublic(ORMModel):
    id: uuid.UUID
    proposal_id: uuid.UUID
    approval_decision_id: uuid.UUID
    created_by_id: uuid.UUID
    title: str
    description: str
    assignee: str | None
    priority: TaskPriority
    due_at: datetime | None
    state: TaskState
    created_at: datetime
    updated_at: datetime


class DecisionAccepted(StrictModel):
    decision: DecisionPublic
    proposal: ProposalPublic
    replacement: ProposalPublic | None
    task: WorkflowTaskPublic | None
    dispatch_job_id: str | None


class TaskList(StrictModel):
    items: list[WorkflowTaskPublic]
    total: int
    offset: int
    limit: int


class TaskPatch(StrictModel):
    state: TaskState | None = None
    assignee: str | None = Field(default=None, min_length=1, max_length=200)
    priority: TaskPriority | None = None
    due_at: datetime | None = None


class AuditEventPublic(ORMModel):
    id: uuid.UUID
    occurred_at: datetime
    actor_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: uuid.UUID | None
    outcome: str
    correlation_id: str
    causation_id: str | None
    thread_id: uuid.UUID | None
    detail: dict[str, Any]


class AuditEventList(StrictModel):
    items: list[AuditEventPublic]
    total: int
    offset: int
    limit: int


@workflow_router.post(
    "/workflow-runs",
    response_model=WorkflowStartAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["workflows"],
)
async def create_workflow_run(
    body: WorkflowRunRequest,
    request: Request,
    actor: CSRFUser,
    db: DBSession,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
) -> WorkflowStartAccepted:
    if not 8 <= len(idempotency_key) <= 128:
        raise AppError("invalid_idempotency_key", "Idempotency-Key must be 8-128 characters")
    if body.document_ids:
        found = int(
            await db.scalar(
                select(func.count())
                .select_from(Document)
                .where(Document.id.in_(body.document_ids), Document.deleted_at.is_(None))
            )
            or 0
        )
        if found != len(set(body.document_ids)):
            raise NotFoundError("Document scope")
    repository: WorkflowRepository = request.app.state.workflow_repository
    run, created = await repository.create_or_get_run(
        db,
        actor=actor,
        question=body.question,
        document_ids=body.document_ids,
        correlation_id=current_correlation_id(),
        idempotency_key=idempotency_key,
    )
    event = await request.app.state.outbox_repository.add(
        db,
        topic="localguard.run_workflow",
        aggregate_type="workflow_run",
        aggregate_id=run.id,
        dedupe_key=f"workflow:{run.id}:start",
        args=[str(run.id)],
        origin_correlation_id=run.origin_correlation_id,
    )
    await request.app.state.audit_repository.add(
        db,
        actor_id=actor.id,
        action="workflow.request",
        resource_type="workflow_run",
        resource_id=run.id,
        outcome="queued",
        correlation_id=run.origin_correlation_id,
        causation_id=str(event.id),
        thread_id=run.id,
        dedupe_key=f"workflow:{run.id}:request",
        detail={"document_count": len(body.document_ids), "created": created},
    )
    await db.commit()
    task_id = await request.app.state.outbox_dispatcher.dispatch_one(event.id)
    return WorkflowStartAccepted(run=WorkflowRunPublic.model_validate(run), dispatch_job_id=task_id)


@workflow_router.get(
    "/workflow-runs/{thread_id}", response_model=WorkflowRunPublic, tags=["workflows"]
)
async def get_workflow_run(
    thread_id: uuid.UUID, request: Request, actor: CurrentUser, db: DBSession
) -> WorkflowRunPublic:
    repository: WorkflowRepository = request.app.state.workflow_repository
    run = await repository.get_run(db, thread_id)
    if run is None:
        raise NotFoundError("Workflow run")
    if actor.role == Role.VIEWER and run.requested_by_id != actor.id:
        raise AuthorizationError()
    return WorkflowRunPublic.model_validate(run)


@workflow_router.get("/findings", response_model=FindingList, tags=["workflows"])
async def list_findings(
    actor: CurrentUser,
    db: DBSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    workflow_run_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    finding_type: FindingType | None = None,
) -> FindingList:
    statement = select(ExtractedFinding).join(
        WorkflowRun, WorkflowRun.id == ExtractedFinding.workflow_run_id
    )
    count_statement = (
        select(func.count())
        .select_from(ExtractedFinding)
        .join(WorkflowRun, WorkflowRun.id == ExtractedFinding.workflow_run_id)
    )
    if actor.role == Role.VIEWER:
        statement = statement.where(WorkflowRun.requested_by_id == actor.id)
        count_statement = count_statement.where(WorkflowRun.requested_by_id == actor.id)
    if workflow_run_id is not None:
        statement = statement.where(WorkflowRun.id == workflow_run_id)
        count_statement = count_statement.where(WorkflowRun.id == workflow_run_id)
    if document_id is not None:
        document_scope = WorkflowRun.document_ids.contains([str(document_id)])
        statement = statement.where(document_scope)
        count_statement = count_statement.where(document_scope)
    if finding_type is not None:
        statement = statement.where(ExtractedFinding.finding_type == finding_type)
        count_statement = count_statement.where(ExtractedFinding.finding_type == finding_type)
    items = list(
        (
            await db.scalars(
                statement.order_by(ExtractedFinding.created_at.desc()).offset(offset).limit(limit)
            )
        ).all()
    )
    total = int(await db.scalar(count_statement) or 0)
    evidence = await _evidence_map(
        db, [chunk_id for item in items for chunk_id in item.cited_chunk_ids]
    )
    return FindingList(
        items=[_finding_public(item, evidence) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@workflow_router.get("/approvals", response_model=ProposalList, tags=["approvals"])
async def list_approvals(
    request: Request,
    actor: ReviewerRead,
    db: DBSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ProposalList:
    await expire_pending_proposals(
        db,
        correlation_id=current_correlation_id(),
        actor_id=actor.id,
        audits=request.app.state.audit_repository,
    )
    await db.commit()
    repository: WorkflowRepository = request.app.state.workflow_repository
    items, total = await repository.list_proposals(db, states=None, offset=offset, limit=limit)
    evidence = await _evidence_map(
        db, [chunk_id for item in items for chunk_id in item.cited_chunk_ids]
    )
    return ProposalList(
        items=[_proposal_public(item, evidence) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@workflow_router.get("/approvals/{proposal_id}", response_model=ProposalPublic, tags=["approvals"])
async def get_approval(
    proposal_id: uuid.UUID,
    request: Request,
    actor: ReviewerRead,
    db: DBSession,
) -> ProposalPublic:
    await expire_pending_proposals(
        db,
        correlation_id=current_correlation_id(),
        actor_id=actor.id,
        audits=request.app.state.audit_repository,
    )
    await db.commit()
    proposal = await request.app.state.workflow_repository.get_proposal(db, proposal_id)
    if proposal is None:
        raise NotFoundError("Proposal")
    return _proposal_public(proposal, await _evidence_map(db, proposal.cited_chunk_ids))


@workflow_router.post(
    "/approvals/{proposal_id}/approve",
    response_model=DecisionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["approvals"],
)
async def approve_proposal(
    proposal_id: uuid.UUID,
    body: ApprovalRequest,
    request: Request,
    actor: ReviewerWrite,
    db: DBSession,
) -> DecisionAccepted:
    return await _decide(proposal_id, DecisionKind.APPROVE, body, request, actor, db)


@workflow_router.post(
    "/approvals/{proposal_id}/reject",
    response_model=DecisionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["approvals"],
)
async def reject_proposal(
    proposal_id: uuid.UUID,
    body: RejectionRequest,
    request: Request,
    actor: ReviewerWrite,
    db: DBSession,
) -> DecisionAccepted:
    return await _decide(proposal_id, DecisionKind.REJECT, body, request, actor, db)


@workflow_router.post(
    "/approvals/{proposal_id}/edit",
    response_model=DecisionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["approvals"],
)
async def edit_proposal(
    proposal_id: uuid.UUID,
    body: EditRequest,
    request: Request,
    actor: ReviewerWrite,
    db: DBSession,
) -> DecisionAccepted:
    return await _decide(proposal_id, DecisionKind.EDIT, body, request, actor, db)


async def _decide(
    proposal_id: uuid.UUID,
    decision: DecisionKind,
    body: ProposalBinding | ProposalEditBinding,
    request: Request,
    actor: User,
    db: AsyncSession,
) -> DecisionAccepted:
    service: WorkflowApprovalService = request.app.state.workflow_approval_service
    outcome = await service.decide(
        db,
        proposal_id=proposal_id,
        actor=actor,
        decision=decision,
        binding=body,
        correlation_id=current_correlation_id(),
    )
    await db.commit()
    task_id = await request.app.state.outbox_dispatcher.dispatch_one(outcome.outbox_event_id)
    task = await db.scalar(
        select(WorkflowTask).where(WorkflowTask.proposal_id == outcome.proposal.id)
    )
    proposal_evidence = await _evidence_map(db, outcome.proposal.cited_chunk_ids)
    replacement_evidence = (
        await _evidence_map(db, outcome.replacement.cited_chunk_ids) if outcome.replacement else {}
    )
    return DecisionAccepted(
        decision=DecisionPublic.model_validate(outcome.decision),
        proposal=_proposal_public(outcome.proposal, proposal_evidence),
        replacement=(
            _proposal_public(outcome.replacement, replacement_evidence)
            if outcome.replacement
            else None
        ),
        task=WorkflowTaskPublic.model_validate(task) if task else None,
        dispatch_job_id=task_id,
    )


@workflow_router.get("/tasks", response_model=TaskList, tags=["tasks"])
async def list_tasks(
    actor: CurrentUser,
    db: DBSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> TaskList:
    statement = (
        select(WorkflowTask)
        .join(ActionProposal, ActionProposal.id == WorkflowTask.proposal_id)
        .join(WorkflowRun, WorkflowRun.id == ActionProposal.workflow_run_id)
    )
    count_statement = (
        select(func.count())
        .select_from(WorkflowTask)
        .join(ActionProposal, ActionProposal.id == WorkflowTask.proposal_id)
        .join(WorkflowRun, WorkflowRun.id == ActionProposal.workflow_run_id)
    )
    if actor.role == Role.VIEWER:
        statement = statement.where(WorkflowRun.requested_by_id == actor.id)
        count_statement = count_statement.where(WorkflowRun.requested_by_id == actor.id)
    items = list(
        (
            await db.scalars(
                statement.order_by(WorkflowTask.created_at.desc()).offset(offset).limit(limit)
            )
        ).all()
    )
    total = int(await db.scalar(count_statement) or 0)
    return TaskList(
        items=[WorkflowTaskPublic.model_validate(item) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@workflow_router.get("/tasks/{task_id}", response_model=WorkflowTaskPublic, tags=["tasks"])
async def get_task(
    task_id: uuid.UUID,
    actor: CurrentUser,
    db: DBSession,
) -> WorkflowTaskPublic:
    row = await db.execute(
        select(WorkflowTask, WorkflowRun.requested_by_id)
        .join(ActionProposal, ActionProposal.id == WorkflowTask.proposal_id)
        .join(WorkflowRun, WorkflowRun.id == ActionProposal.workflow_run_id)
        .where(WorkflowTask.id == task_id)
    )
    item = row.one_or_none()
    if item is None:
        raise NotFoundError("Workflow task")
    task, requested_by_id = item
    if actor.role == Role.VIEWER and requested_by_id != actor.id:
        raise AuthorizationError()
    return WorkflowTaskPublic.model_validate(task)


@workflow_router.patch("/tasks/{task_id}", response_model=WorkflowTaskPublic, tags=["tasks"])
async def update_task(
    task_id: uuid.UUID,
    body: TaskPatch,
    request: Request,
    actor: ReviewerWrite,
    db: DBSession,
) -> WorkflowTaskPublic:
    task = await request.app.state.workflow_approval_service.update_task(
        db,
        task_id=task_id,
        actor=actor,
        state=body.state,
        assignee=body.assignee,
        priority=body.priority,
        due_at=body.due_at,
        correlation_id=current_correlation_id(),
    )
    return WorkflowTaskPublic.model_validate(task)


@workflow_router.get("/audit-events", response_model=AuditEventList, tags=["audit"])
async def list_audit_events(
    actor: ReviewerRead,
    db: DBSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> AuditEventList:
    del actor
    items = list(
        (
            await db.scalars(
                select(AuditEvent)
                .order_by(AuditEvent.occurred_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
    )
    total = int(await db.scalar(select(func.count()).select_from(AuditEvent)) or 0)
    return AuditEventList(
        items=[_audit_public(item) for item in items], total=total, offset=offset, limit=limit
    )


@workflow_router.get("/audit-events/{event_id}", response_model=AuditEventPublic, tags=["audit"])
async def get_audit_event(
    event_id: uuid.UUID, actor: ReviewerRead, db: DBSession
) -> AuditEventPublic:
    del actor
    event = await db.get(AuditEvent, event_id)
    if event is None:
        raise NotFoundError("Audit event")
    return _audit_public(event)


def _audit_public(event: AuditEvent) -> AuditEventPublic:
    return AuditEventPublic(
        id=event.id,
        occurred_at=event.occurred_at,
        actor_id=event.actor_id,
        action=event.action,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        outcome=event.outcome,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
        thread_id=event.thread_id,
        detail=_redact_detail(event.detail),
    )


def _redact_detail(value: dict[str, Any]) -> dict[str, Any]:
    blocked = ("password", "secret", "token", "content")
    return {
        key: "[REDACTED]" if any(term in key.casefold() for term in blocked) else item
        for key, item in value.items()
    }


async def _evidence_map(
    db: AsyncSession, stable_ids: list[str]
) -> dict[str, EvidenceReferencePublic]:
    unique_ids = list(dict.fromkeys(stable_ids))
    if not unique_ids:
        return {}
    chunks = list((await db.scalars(select(Chunk).where(Chunk.stable_id.in_(unique_ids)))).all())
    resolved: dict[str, EvidenceReferencePublic] = {}
    for chunk in chunks:
        resolved.setdefault(
            chunk.stable_id,
            EvidenceReferencePublic(
                chunk_id=chunk.stable_id,
                available=True,
                document_id=chunk.revision.document_id,
                revision_id=chunk.revision_id,
                document_title=chunk.revision.document.title,
                anchor_key=chunk.anchor.stable_key,
                anchor_label=chunk.anchor.label,
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                excerpt=chunk.content[:1000],
            ),
        )
    return resolved


def _evidence_for(
    stable_ids: list[str], evidence: dict[str, EvidenceReferencePublic]
) -> list[EvidenceReferencePublic]:
    return [
        evidence.get(
            stable_id,
            EvidenceReferencePublic(chunk_id=stable_id, available=False),
        )
        for stable_id in stable_ids
    ]


def _finding_public(
    finding: ExtractedFinding, evidence: dict[str, EvidenceReferencePublic]
) -> FindingPublic:
    return FindingPublic(
        **FindingPublic.model_validate(finding).model_dump(exclude={"evidence"}),
        evidence=_evidence_for(finding.cited_chunk_ids, evidence),
    )


def _proposal_public(
    proposal: ActionProposal, evidence: dict[str, EvidenceReferencePublic]
) -> ProposalPublic:
    return ProposalPublic(
        **ProposalPublic.model_validate(proposal).model_dump(exclude={"evidence"}),
        evidence=_evidence_for(proposal.cited_chunk_ids, evidence),
    )
