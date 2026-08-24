"""Transactional persistence and approval policy for workflow orchestration."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from ..config import Settings
from ..dispatch import OutboxRepository, outbox_repository
from ..errors import AuthorizationError, ConflictError, NotFoundError
from ..models import (
    ActionProposal,
    ApprovalDecision,
    AuditEvent,
    DecisionKind,
    Document,
    DocumentState,
    ExtractedFinding,
    ProposalState,
    Role,
    TaskPriority,
    TaskState,
    User,
    WorkflowRun,
    WorkflowState,
    WorkflowTask,
    utc_now,
)
from ..repositories import AuditRepository, audit_repository
from ..retrieval import EvidenceResolver, evidence_resolver
from .contracts import FindingDraft, TaskProposalDraft

MCP_DIRECT_WORKFLOW_INTENT = "mcp_direct_workflow_action"


def canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def request_hash(question: str, document_ids: list[uuid.UUID]) -> str:
    return canonical_hash(
        {"question": question, "document_ids": sorted(str(item) for item in document_ids)}
    )


def compute_evidence_snapshot_hash(evidence: Iterable[tuple[str, str]]) -> str:
    """Bind a proposal to its cited stable IDs and exact authoritative contents."""

    snapshot = [
        {
            "chunk_id": chunk_id,
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }
        for chunk_id, content in sorted(evidence)
    ]
    return canonical_hash(snapshot)


def workflow_execution_lock_key(run_id: uuid.UUID) -> int:
    material = hashlib.sha256(b"workflow-run:" + run_id.bytes).digest()[:8]
    return int.from_bytes(material, "big", signed=True)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProposalBinding(StrictModel):
    version: int = Field(ge=1)
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    comment: str | None = Field(default=None, max_length=1000)


class ProposalEditBinding(ProposalBinding):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    assignee: str | None = Field(default=None, max_length=200)
    priority: TaskPriority | None = None
    due_at: datetime | None = None
    reasoning_summary: str | None = Field(default=None, min_length=1, max_length=1000)


@dataclass(frozen=True, slots=True)
class DecisionOutcome:
    decision: ApprovalDecision
    proposal: ActionProposal
    replacement: ActionProposal | None
    outbox_event_id: uuid.UUID


class WorkflowRepository:
    async def create_run(
        self,
        db: AsyncSession,
        *,
        actor: User,
        question: str,
        document_ids: list[uuid.UUID],
        correlation_id: str,
        idempotency_key: str | None = None,
    ) -> WorkflowRun:
        await self._lock_document_scope(db, document_ids)
        key = idempotency_key or f"internal-{uuid.uuid4().hex}"
        run = WorkflowRun(
            id=uuid.uuid4(),
            requested_by_id=actor.id,
            idempotency_key=key,
            question=question,
            document_ids=[str(value) for value in document_ids],
            request_hash=request_hash(question, document_ids),
            origin_correlation_id=correlation_id,
            state=WorkflowState.RUNNING,
        )
        db.add(run)
        await db.flush()
        return run

    async def create_or_get_run(
        self,
        db: AsyncSession,
        *,
        actor: User,
        question: str,
        document_ids: list[uuid.UUID],
        correlation_id: str,
        idempotency_key: str,
    ) -> tuple[WorkflowRun, bool]:
        payload_hash = request_hash(question, document_ids)
        existing = cast(
            WorkflowRun | None,
            await db.scalar(
                select(WorkflowRun).where(
                    WorkflowRun.requested_by_id == actor.id,
                    WorkflowRun.idempotency_key == idempotency_key,
                )
            ),
        )
        if existing is not None:
            if existing.request_hash != payload_hash:
                raise ConflictError(
                    "idempotency_payload_mismatch",
                    "Idempotency-Key was already used for a different workflow payload",
                )
            return existing, False
        await self._lock_document_scope(db, document_ids)
        run_id = uuid.uuid4()
        now = utc_now()
        inserted_id = await db.scalar(
            pg_insert(WorkflowRun)
            .values(
                id=run_id,
                requested_by_id=actor.id,
                idempotency_key=idempotency_key,
                question=question,
                document_ids=[str(value) for value in document_ids],
                request_hash=payload_hash,
                origin_correlation_id=correlation_id,
                state=WorkflowState.RUNNING,
                cited_chunk_ids=[],
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(
                index_elements=[WorkflowRun.requested_by_id, WorkflowRun.idempotency_key]
            )
            .returning(WorkflowRun.id)
        )
        run = cast(
            WorkflowRun | None,
            await db.scalar(
                select(WorkflowRun).where(
                    WorkflowRun.requested_by_id == actor.id,
                    WorkflowRun.idempotency_key == idempotency_key,
                )
            ),
        )
        if run is None:
            raise RuntimeError("workflow run upsert did not produce a row")
        if run.request_hash != payload_hash:
            raise ConflictError(
                "idempotency_payload_mismatch",
                "Idempotency-Key was already used for a different workflow payload",
            )
        return run, inserted_id == run_id

    async def _lock_document_scope(self, db: AsyncSession, document_ids: list[uuid.UUID]) -> None:
        if not document_ids:
            return
        found = set(
            (
                await db.scalars(
                    select(Document.id)
                    .where(
                        Document.id.in_(document_ids),
                        Document.deleted_at.is_(None),
                        Document.state == DocumentState.READY,
                    )
                    .with_for_update(of=Document)
                )
            ).all()
        )
        if found != set(document_ids):
            raise NotFoundError("Document scope")

    async def get_run(
        self, db: AsyncSession, run_id: uuid.UUID, *, lock: bool = False
    ) -> WorkflowRun | None:
        statement = select(WorkflowRun).where(WorkflowRun.id == run_id)
        if lock:
            statement = statement.with_for_update()
        return cast(WorkflowRun | None, await db.scalar(statement))

    async def persist_analysis(
        self,
        db: AsyncSession,
        *,
        run_id: uuid.UUID,
        intent: str,
        answer: str,
        insufficient: bool,
        cited_chunk_ids: list[str],
        findings: list[FindingDraft],
    ) -> WorkflowRun:
        run = await self.get_run(db, run_id, lock=True)
        if run is None:
            raise NotFoundError("Workflow run")
        target_state = WorkflowState.INSUFFICIENT if insufficient else WorkflowState.RUNNING
        if run.state != WorkflowState.RUNNING:
            if (
                run.intent == intent
                and run.answer_text == answer
                and run.insufficient_evidence == insufficient
                and run.cited_chunk_ids == list(cited_chunk_ids)
            ):
                return run
            raise ConflictError(
                "workflow_not_running", "Workflow analysis cannot overwrite persisted state"
            )
        run.intent = intent
        run.answer_text = answer
        run.insufficient_evidence = insufficient
        run.cited_chunk_ids = list(cited_chunk_ids)
        run.state = target_state
        now = utc_now()
        for finding in findings:
            payload = finding.model_dump(mode="json")
            stable_hash = canonical_hash(payload)
            await db.execute(
                pg_insert(ExtractedFinding)
                .values(
                    id=uuid.uuid4(),
                    workflow_run_id=run.id,
                    finding_type=finding.finding_type,
                    summary=finding.summary,
                    normalized_value=finding.normalized_value,
                    responsible_party=finding.responsible_party,
                    due_date=finding.due_date,
                    severity=finding.severity,
                    cited_chunk_ids=finding.cited_chunk_ids,
                    cited_marker_ids=finding.cited_marker_ids,
                    fields=finding.fields,
                    origin=finding.origin,
                    normalizer_version=finding.normalizer_version,
                    source_marker_sha256=finding.source_marker_sha256,
                    derivation_reason=finding.derivation_reason,
                    stable_hash=stable_hash,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        ExtractedFinding.workflow_run_id,
                        ExtractedFinding.stable_hash,
                    ]
                )
            )
        await db.flush()
        return run

    async def upsert_proposal(
        self,
        db: AsyncSession,
        *,
        run_id: uuid.UUID,
        actor_id: uuid.UUID,
        draft: TaskProposalDraft,
        evidence_snapshot_hash: str,
    ) -> ActionProposal:
        run = await self.get_run(db, run_id, lock=True)
        if run is None:
            raise NotFoundError("Workflow run")
        payload = _proposal_payload(draft)
        payload_hash = canonical_hash(payload)
        existing = await db.scalar(
            select(ActionProposal).where(
                ActionProposal.workflow_run_id == run.id,
                ActionProposal.payload_hash == payload_hash,
            )
        )
        if existing is not None:
            if existing.evidence_snapshot_hash != evidence_snapshot_hash:
                raise ConflictError(
                    "proposal_binding_mismatch", "Proposal evidence binding changed"
                )
            _validated_proposal_draft(existing)
            allowed_pairs = {
                (WorkflowState.WAITING_APPROVAL, ProposalState.PENDING),
                (WorkflowState.COMPLETED, ProposalState.EXECUTED),
                (WorkflowState.REJECTED, ProposalState.REJECTED),
                (WorkflowState.FAILED, ProposalState.FAILED),
            }
            if (run.state, existing.state) not in allowed_pairs:
                raise ConflictError("workflow_state_conflict", "Existing proposal is not startable")
            return existing
        if run.state != WorkflowState.RUNNING:
            raise ConflictError("workflow_not_running", "Workflow is not startable")
        next_version = (
            int(
                await db.scalar(
                    select(func.coalesce(func.max(ActionProposal.version), 0)).where(
                        ActionProposal.workflow_run_id == run.id
                    )
                )
                or 0
            )
            + 1
        )
        proposal = ActionProposal(
            workflow_run_id=run.id,
            created_by_id=actor_id,
            version=next_version,
            title=draft.title,
            description=draft.description,
            assignee=draft.assignee,
            priority=draft.priority,
            due_at=draft.due_at,
            reasoning_summary=draft.reasoning_summary,
            cited_chunk_ids=list(draft.cited_chunk_ids),
            canonical_payload=payload,
            payload_hash=payload_hash,
            evidence_snapshot_hash=evidence_snapshot_hash,
            expires_at=utc_now() + timedelta(minutes=self.settings.proposal_ttl_minutes),
        )
        db.add(proposal)
        run.state = WorkflowState.WAITING_APPROVAL
        await db.flush()
        return proposal

    async def get_proposal(
        self, db: AsyncSession, proposal_id: uuid.UUID, *, lock: bool = False
    ) -> ActionProposal | None:
        statement = select(ActionProposal).where(ActionProposal.id == proposal_id)
        if lock:
            statement = statement.with_for_update()
        return cast(ActionProposal | None, await db.scalar(statement))

    async def list_proposals(
        self,
        db: AsyncSession,
        *,
        states: list[ProposalState] | None,
        offset: int,
        limit: int,
    ) -> tuple[list[ActionProposal], int]:
        predicate: list[ColumnElement[bool]] = (
            [] if states is None else [ActionProposal.state.in_(states)]
        )
        if states is not None and ProposalState.PENDING in states:
            predicate.append(ActionProposal.expires_at > utc_now())
        items = list(
            (
                await db.scalars(
                    select(ActionProposal)
                    .where(*predicate)
                    .order_by(ActionProposal.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )
        total = int(
            await db.scalar(select(func.count()).select_from(ActionProposal).where(*predicate)) or 0
        )
        return items, total

    async def list_findings(
        self, db: AsyncSession, *, offset: int, limit: int
    ) -> tuple[list[ExtractedFinding], int]:
        items = list(
            (
                await db.scalars(
                    select(ExtractedFinding)
                    .order_by(ExtractedFinding.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )
        total = int(await db.scalar(select(func.count()).select_from(ExtractedFinding)) or 0)
        return items, total

    async def list_tasks(
        self, db: AsyncSession, *, offset: int, limit: int
    ) -> tuple[list[WorkflowTask], int]:
        items = list(
            (
                await db.scalars(
                    select(WorkflowTask)
                    .order_by(WorkflowTask.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )
        total = int(await db.scalar(select(func.count()).select_from(WorkflowTask)) or 0)
        return items, total

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def mark_failed(
        self,
        db: AsyncSession,
        *,
        run_id: uuid.UUID,
        code: str,
        detail: str,
    ) -> WorkflowRun | None:
        run = await self.get_run(db, run_id, lock=True)
        if run is None:
            return None
        if run.state in {
            WorkflowState.COMPLETED,
            WorkflowState.REJECTED,
            WorkflowState.INSUFFICIENT,
        }:
            return run
        run.state = WorkflowState.FAILED
        run.error_code = code[:80]
        run.error_detail = detail[:500]
        await db.flush()
        return run


class WorkflowApprovalService:
    def __init__(
        self,
        settings: Settings,
        repository: WorkflowRepository,
        audits: AuditRepository = audit_repository,
        outbox: OutboxRepository = outbox_repository,
        resolver: EvidenceResolver = evidence_resolver,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.audits = audits
        self.outbox = outbox
        self.resolver = resolver

    async def decide(
        self,
        db: AsyncSession,
        *,
        proposal_id: uuid.UUID,
        actor: User,
        decision: DecisionKind,
        binding: ProposalBinding | ProposalEditBinding,
        correlation_id: str,
    ) -> DecisionOutcome:
        if actor.role not in {Role.REVIEWER, Role.ADMIN} or not actor.is_active:
            raise AuthorizationError()
        proposal = await self.repository.get_proposal(db, proposal_id, lock=True)
        if proposal is None:
            raise NotFoundError("Proposal")
        if proposal.state != ProposalState.PENDING:
            raise ConflictError("proposal_not_pending", "Proposal is no longer pending")
        if proposal.expires_at <= utc_now():
            proposal.state = ProposalState.EXPIRED
            run = await self.repository.get_run(db, proposal.workflow_run_id, lock=True)
            if run is not None and run.state == WorkflowState.WAITING_APPROVAL:
                run.state = WorkflowState.FAILED
                run.error_code = "proposal_expired"
                run.error_detail = "The pending action proposal expired before review"
            await self.audits.add(
                db,
                actor_id=actor.id,
                action="proposal.expire",
                resource_type="action_proposal",
                resource_id=proposal.id,
                outcome="expired",
                correlation_id=correlation_id,
                thread_id=proposal.workflow_run_id,
            )
            await db.commit()
            raise ConflictError("proposal_expired", "Proposal has expired")
        self._validate_binding(proposal, binding)

        replacement: ActionProposal | None = None
        if decision == DecisionKind.EDIT:
            if not isinstance(binding, ProposalEditBinding):
                raise ConflictError("edit_payload_missing", "An edit decision requires a patch")
            replacement = await self._create_replacement(db, proposal, actor, binding)
            proposal.state = ProposalState.INVALIDATED
        elif decision == DecisionKind.APPROVE:
            proposal.state = ProposalState.APPROVED
        else:
            proposal.state = ProposalState.REJECTED

        decision_row = ApprovalDecision(
            proposal_id=proposal.id,
            proposal_version=proposal.version,
            decided_by_id=actor.id,
            decision=decision,
            payload_hash=proposal.payload_hash,
            evidence_snapshot_hash=proposal.evidence_snapshot_hash,
            comment=binding.comment,
            replacement_proposal_id=replacement.id if replacement else None,
        )
        db.add(decision_row)
        await db.flush()
        event = await self.outbox.add(
            db,
            topic="localguard.resume_workflow",
            aggregate_type="workflow_run",
            aggregate_id=proposal.workflow_run_id,
            dedupe_key=f"resume:{decision_row.id}",
            args=[str(decision_row.id)],
            origin_correlation_id=correlation_id,
        )
        await self.audits.add(
            db,
            actor_id=actor.id,
            action=f"proposal.{decision.value}",
            resource_type="action_proposal",
            resource_id=proposal.id,
            outcome=proposal.state.value,
            correlation_id=correlation_id,
            causation_id=str(decision_row.id),
            thread_id=proposal.workflow_run_id,
            detail={
                "version": proposal.version,
                "payload_hash": proposal.payload_hash,
                "evidence_snapshot_hash": proposal.evidence_snapshot_hash,
                "replacement_proposal_id": str(replacement.id) if replacement else None,
                "outbox_event_id": str(event.id),
            },
        )
        await db.flush()
        return DecisionOutcome(decision_row, proposal, replacement, event.id)

    async def execute_approved(
        self,
        db: AsyncSession,
        *,
        thread_id: uuid.UUID,
        decision_id: uuid.UUID,
        proposal_id: uuid.UUID,
        proposal_version: int,
        payload_hash: str,
        evidence_snapshot_hash: str,
        correlation_id: str,
    ) -> WorkflowTask:
        decision = await db.get(ApprovalDecision, decision_id, with_for_update=True)
        proposal = await self.repository.get_proposal(db, proposal_id, lock=True)
        if decision is None or proposal is None:
            raise ConflictError("approval_binding_invalid", "Approval binding was not found")
        run = await self.repository.get_run(db, thread_id, lock=True)
        reviewer = await db.get(User, decision.decided_by_id)
        if (
            run is None
            or proposal.workflow_run_id != run.id
            or decision.proposal_id != proposal.id
            or decision.decision != DecisionKind.APPROVE
            or proposal.version != proposal_version
            or decision.proposal_version != proposal_version
            or proposal.payload_hash != payload_hash
            or decision.payload_hash != payload_hash
            or proposal.evidence_snapshot_hash != evidence_snapshot_hash
            or decision.evidence_snapshot_hash != evidence_snapshot_hash
            or reviewer is None
            or not reviewer.is_active
            or reviewer.role not in {Role.REVIEWER, Role.ADMIN}
        ):
            raise ConflictError("approval_binding_invalid", "Approval binding is no longer valid")
        existing = cast(
            WorkflowTask | None,
            await db.scalar(select(WorkflowTask).where(WorkflowTask.proposal_id == proposal.id)),
        )
        if existing is not None:
            decision.applied_at = decision.applied_at or utc_now()
            return existing
        if proposal.state != ProposalState.APPROVED:
            raise ConflictError("proposal_not_approved", "Proposal is not approved")
        try:
            draft = _validated_proposal_draft(proposal)
        except ConflictError as exc:
            await self._fail_execution(
                db,
                run=run,
                proposal=proposal,
                decision=decision,
                actor_id=reviewer.id,
                correlation_id=correlation_id,
                code=exc.code,
            )
            raise
        resolved = await self.resolver.resolve_chunks(db, list(draft.cited_chunk_ids))
        current_evidence_hash = compute_evidence_snapshot_hash(
            (chunk_id, chunk.content) for chunk_id, chunk in resolved.items()
        )
        if (
            len(resolved) != len(draft.cited_chunk_ids)
            or set(resolved) != set(draft.cited_chunk_ids)
            or current_evidence_hash != evidence_snapshot_hash
        ):
            await self._fail_execution(
                db,
                run=run,
                proposal=proposal,
                decision=decision,
                actor_id=reviewer.id,
                correlation_id=correlation_id,
                code="approval_evidence_invalid",
            )
            raise ConflictError(
                "approval_evidence_invalid", "Approved evidence is no longer authoritative"
            )
        task = WorkflowTask(
            proposal_id=proposal.id,
            approval_decision_id=decision.id,
            created_by_id=reviewer.id,
            title=draft.title,
            description=draft.description,
            assignee=draft.assignee,
            priority=draft.priority,
            due_at=draft.due_at,
            state=TaskState.OPEN,
        )
        db.add(task)
        proposal.state = ProposalState.EXECUTED
        run.state = WorkflowState.COMPLETED
        await db.flush()
        await self.audits.add(
            db,
            actor_id=reviewer.id,
            action="workflow_task.create",
            resource_type="workflow_task",
            resource_id=task.id,
            outcome="succeeded",
            correlation_id=correlation_id,
            causation_id=str(decision.id),
            thread_id=run.id,
            detail={
                "proposal_id": str(proposal.id),
                "proposal_version": proposal.version,
                "payload_hash": proposal.payload_hash,
            },
        )
        decision.applied_at = utc_now()
        return task

    async def finalize_rejection(
        self,
        db: AsyncSession,
        *,
        thread_id: uuid.UUID,
        decision_id: uuid.UUID,
        proposal_id: uuid.UUID,
    ) -> None:
        decision = await db.get(ApprovalDecision, decision_id)
        proposal = await self.repository.get_proposal(db, proposal_id)
        run = await self.repository.get_run(db, thread_id, lock=True)
        if (
            decision is None
            or proposal is None
            or run is None
            or decision.decision != DecisionKind.REJECT
            or decision.proposal_id != proposal.id
            or proposal.workflow_run_id != run.id
            or proposal.state != ProposalState.REJECTED
        ):
            raise ConflictError("rejection_binding_invalid", "Rejection binding is invalid")
        run.state = WorkflowState.REJECTED
        decision.applied_at = decision.applied_at or utc_now()
        await db.flush()

    async def mark_edit_applied(
        self,
        db: AsyncSession,
        *,
        thread_id: uuid.UUID,
        decision_id: uuid.UUID,
        replacement_proposal_id: uuid.UUID,
    ) -> None:
        decision = await db.get(ApprovalDecision, decision_id, with_for_update=True)
        replacement = await self.repository.get_proposal(db, replacement_proposal_id)
        if (
            decision is None
            or replacement is None
            or decision.decision != DecisionKind.EDIT
            or decision.replacement_proposal_id != replacement.id
            or replacement.workflow_run_id != thread_id
            or replacement.state != ProposalState.PENDING
        ):
            raise ConflictError("edit_binding_invalid", "Edit replacement binding is invalid")
        decision.applied_at = decision.applied_at or utc_now()
        await db.flush()

    async def update_task(
        self,
        db: AsyncSession,
        *,
        task_id: uuid.UUID,
        actor: User,
        state: TaskState | None,
        assignee: str | None,
        priority: TaskPriority | None,
        due_at: datetime | None,
        correlation_id: str,
    ) -> WorkflowTask:
        if actor.role not in {Role.REVIEWER, Role.ADMIN} or not actor.is_active:
            raise AuthorizationError()
        task = await db.get(WorkflowTask, task_id, with_for_update=True)
        if task is None:
            raise NotFoundError("Workflow task")
        changes: dict[str, Any] = {}
        if state is not None:
            task.state = state
            changes["state"] = state.value
        if assignee is not None:
            task.assignee = assignee
            changes["assignee"] = assignee
        if priority is not None:
            task.priority = priority
            changes["priority"] = priority.value
        if due_at is not None:
            if due_at.tzinfo is None or due_at.utcoffset() is None:
                raise ConflictError("invalid_due_at", "Task due_at must include a timezone")
            task.due_at = due_at.astimezone(UTC)
            changes["due_at"] = task.due_at.isoformat()
        if not changes:
            raise ConflictError("empty_task_patch", "Task patch did not contain a change")
        await self.audits.add(
            db,
            actor_id=actor.id,
            action="workflow_task.update",
            resource_type="workflow_task",
            resource_id=task.id,
            outcome="succeeded",
            correlation_id=correlation_id,
            detail=changes,
        )
        await db.flush()
        return task

    def _validate_binding(self, proposal: ActionProposal, binding: ProposalBinding) -> None:
        _validated_proposal_draft(proposal)
        if (
            proposal.version != binding.version
            or proposal.payload_hash != binding.payload_hash
            or proposal.evidence_snapshot_hash != binding.evidence_snapshot_hash
        ):
            raise ConflictError(
                "proposal_binding_mismatch", "Proposal version or evidence binding changed"
            )

    async def _fail_execution(
        self,
        db: AsyncSession,
        *,
        run: WorkflowRun,
        proposal: ActionProposal,
        decision: ApprovalDecision,
        actor_id: uuid.UUID,
        correlation_id: str,
        code: str,
    ) -> None:
        proposal.state = ProposalState.FAILED
        run.state = WorkflowState.FAILED
        run.error_code = code[:80]
        run.error_detail = "Approved task execution was blocked by an integrity check"
        await self.audits.add(
            db,
            actor_id=actor_id,
            action="workflow_task.create",
            resource_type="action_proposal",
            resource_id=proposal.id,
            outcome="blocked",
            correlation_id=correlation_id,
            causation_id=str(decision.id),
            thread_id=run.id,
            detail={"error_code": code},
        )
        await db.commit()

    async def _create_replacement(
        self,
        db: AsyncSession,
        proposal: ActionProposal,
        actor: User,
        binding: ProposalEditBinding,
    ) -> ActionProposal:
        payload = dict(proposal.canonical_payload)
        patch = binding.model_dump(
            mode="json",
            exclude_none=True,
            exclude={"version", "payload_hash", "evidence_snapshot_hash", "comment"},
        )
        payload.update(patch)
        draft = TaskProposalDraft.model_validate(payload)
        replacement_payload = _proposal_payload(draft)
        replacement_hash = canonical_hash(replacement_payload)
        if replacement_hash == proposal.payload_hash:
            raise ConflictError("empty_proposal_edit", "Proposal edit did not change the payload")
        replacement = ActionProposal(
            workflow_run_id=proposal.workflow_run_id,
            created_by_id=actor.id,
            previous_proposal_id=proposal.id,
            version=proposal.version + 1,
            title=draft.title,
            description=draft.description,
            assignee=draft.assignee,
            priority=draft.priority,
            due_at=draft.due_at,
            reasoning_summary=draft.reasoning_summary,
            cited_chunk_ids=list(draft.cited_chunk_ids),
            canonical_payload=replacement_payload,
            payload_hash=replacement_hash,
            evidence_snapshot_hash=proposal.evidence_snapshot_hash,
            expires_at=utc_now() + timedelta(minutes=self.settings.proposal_ttl_minutes),
        )
        db.add(replacement)
        await db.flush()
        return replacement


def _proposal_payload(draft: TaskProposalDraft) -> dict[str, object]:
    return cast(dict[str, object], draft.model_dump(mode="json"))


def _validated_proposal_draft(proposal: ActionProposal) -> TaskProposalDraft:
    try:
        draft = TaskProposalDraft.model_validate(proposal.canonical_payload)
    except ValidationError as exc:
        raise ConflictError(
            "proposal_payload_invalid", "Proposal payload no longer validates"
        ) from exc
    canonical_payload = _proposal_payload(draft)
    if (
        proposal.canonical_payload != canonical_payload
        or canonical_hash(canonical_payload) != proposal.payload_hash
        or proposal.title != draft.title
        or proposal.description != draft.description
        or proposal.assignee != draft.assignee
        or proposal.priority != draft.priority
        or proposal.due_at != draft.due_at
        or proposal.reasoning_summary != draft.reasoning_summary
        or proposal.cited_chunk_ids != list(draft.cited_chunk_ids)
    ):
        raise ConflictError("proposal_payload_invalid", "Proposal payload integrity check failed")
    return draft


async def expire_pending_proposals(
    db: AsyncSession,
    *,
    correlation_id: str,
    actor_id: uuid.UUID | None,
    audits: AuditRepository = audit_repository,
) -> int:
    proposals = list(
        (
            await db.scalars(
                select(ActionProposal)
                .where(
                    ActionProposal.state == ProposalState.PENDING,
                    ActionProposal.expires_at <= utc_now(),
                )
                .order_by(ActionProposal.expires_at, ActionProposal.id)
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    for proposal in proposals:
        proposal.state = ProposalState.EXPIRED
        run = await db.get(WorkflowRun, proposal.workflow_run_id, with_for_update=True)
        if run is not None and run.state == WorkflowState.WAITING_APPROVAL:
            run.state = WorkflowState.FAILED
            run.error_code = "proposal_expired"
            run.error_detail = "The pending action proposal expired before review"
        await audits.add(
            db,
            actor_id=actor_id,
            action="proposal.expire",
            resource_type="action_proposal",
            resource_id=proposal.id,
            outcome="expired",
            correlation_id=correlation_id,
            thread_id=proposal.workflow_run_id,
            dedupe_key=f"proposal:{proposal.id}:expired",
        )
    await db.flush()
    return len(proposals)


async def list_audit_events(
    db: AsyncSession, *, offset: int, limit: int
) -> tuple[list[AuditEvent], int]:
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
    return items, total
