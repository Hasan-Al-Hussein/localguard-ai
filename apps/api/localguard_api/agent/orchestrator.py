"""Inspectible LangGraph workflow with a durable human approval boundary."""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, RetryPolicy, interrupt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..database import Database
from ..errors import (
    AppError,
    ConflictError,
    NotFoundError,
    RetryableServiceUnavailableError,
    ServiceUnavailableError,
)
from ..models import (
    ActionProposal,
    ApprovalDecision,
    OutboxEvent,
    User,
    WorkflowRun,
    WorkflowState,
)
from ..providers import (
    INSUFFICIENT_ANSWER,
    ChatProvider,
    Evidence,
    QAContextVerdict,
    assess_qa_context,
    validate_action_claim_grounding,
)
from ..repositories import AuditRepository, audit_repository
from ..retrieval import EvidenceResolver, HybridRetriever, evidence_resolver
from .contracts import (
    ApprovalResume,
    ClaimDraft,
    FindingDraft,
    RetrievalState,
    TaskProposalDraft,
    WorkflowGraphState,
    WorkflowModelOutput,
)
from .persistence import (
    MCP_DIRECT_WORKFLOW_INTENT,
    WorkflowApprovalService,
    WorkflowRepository,
    compute_evidence_snapshot_hash,
    workflow_execution_lock_key,
)

_ACTION_TERMS = (
    "propose a task",
    "propose task",
    "propose a workflow task",
    "create a task",
    "create task",
    "add a task",
    "assign a task",
    "schedule a task",
    "make a task",
    "create an action item",
    "add an action item",
    "set a reminder",
    "follow-up task",
    "follow up task",
)
_EXTRACTION_TERMS = (
    "extract",
    "obligation",
    "deadline",
    "responsible party",
    "required action",
    "risk",
)
_ACTION_PATTERN = re.compile(
    r"\b(?:propose|create|add|assign|schedule|make|set)\b.{0,120}"
    r"\b(?:task|action item|reminder)\b"
)
_MARKER_PATTERN = re.compile(r"\bLG-(?:POL|ATK)-[0-9]{3}:L[0-9]{3}\b")
_SOURCE_PATTERN = re.compile(r"\bLG-(?:POL|ATK)-[0-9]{3}\b", re.IGNORECASE)


def _classify_request(question: str) -> tuple[str, bool]:
    """Classify once so graph routing and model transport cannot select different modes."""

    normalized = " ".join(question.casefold().split())
    action_requested = _is_action_request(normalized)
    if action_requested:
        return "workflow_action", True
    if any(term in normalized for term in _EXTRACTION_TERMS):
        return "structured_extraction", False
    return "document_question", False


def _normalize_workflow_output(output: WorkflowModelOutput) -> WorkflowModelOutput:
    """Enforce abstention and artifact policy at the graph boundary for every provider."""

    if output.insufficient_evidence:
        if (
            output.cited_chunk_ids
            or output.cited_marker_ids
            or output.claims
            or output.findings
            or output.proposed_task is not None
        ):
            raise ServiceUnavailableError(
                "model_citation_invalid",
                "An insufficient workflow result cannot contain grounded artifacts",
            )
        return output.model_copy(update={"answer": INSUFFICIENT_ANSWER})
    answer = output.answer.strip()
    if not answer or len(answer) > 8000:
        raise ServiceUnavailableError(
            "model_answer_invalid", "The local model returned an invalid workflow answer"
        )
    return output.model_copy(update={"answer": answer})


class WorkflowOrchestrator:
    """Runs the real graph; application services retain every permission and side effect."""

    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        retriever: HybridRetriever,
        chat: ChatProvider,
        checkpointer: BaseCheckpointSaver[Any],
        repository: WorkflowRepository | None = None,
        approval_service: WorkflowApprovalService | None = None,
        audits: AuditRepository = audit_repository,
        resolver: EvidenceResolver = evidence_resolver,
    ) -> None:
        self.settings = settings
        self.database = database
        self.retriever = retriever
        self.chat = chat
        self.repository = repository or WorkflowRepository(settings)
        self.approvals = approval_service or WorkflowApprovalService(settings, self.repository)
        self.audits = audits
        self.resolver = resolver
        self.graph = self._compile(checkpointer)

    async def start(
        self, run_id: uuid.UUID, *, terminal_on_transient_failure: bool = True
    ) -> WorkflowGraphState:
        async with self._execution_lock(run_id):
            async with self.database.sessions() as db:
                run = await self.repository.get_run(db, run_id)
                if run is None:
                    raise NotFoundError("Workflow run")
                if not _is_startable_state(run.state):
                    return await self.snapshot(run.id)
                requested_by_id = run.requested_by_id
                question = run.question
                document_ids = list(run.document_ids)
                origin_correlation_id = run.origin_correlation_id
            try:
                async with self.database.sessions() as db:
                    actor = await db.get(User, requested_by_id)
                if actor is None or not actor.is_active:
                    raise ConflictError("workflow_actor_inactive", "Workflow actor is inactive")
                initial: WorkflowGraphState = {
                    "thread_id": str(run_id),
                    "actor_id": str(actor.id),
                    "actor_role": actor.role.value,
                    "question": question,
                    "document_ids": document_ids,
                    "origin_correlation_id": origin_correlation_id,
                    "stage_latency_ms": {},
                    "tool_trace": [],
                    "applied_decision_ids": [],
                }
                result = await self.graph.ainvoke(initial, self._config(run_id))
            except ServiceUnavailableError as exc:
                if not isinstance(exc, RetryableServiceUnavailableError) or (
                    terminal_on_transient_failure
                ):
                    await self._record_failure(run_id, exc)
                raise
            except Exception as exc:
                await self._record_failure(run_id, exc)
                raise
            return cast(WorkflowGraphState, result)

    async def resume_decision(
        self, decision_id: uuid.UUID, *, terminal_on_transient_failure: bool = True
    ) -> WorkflowGraphState:
        async with self.database.sessions() as db:
            decision = await db.get(ApprovalDecision, decision_id)
            if decision is None:
                raise NotFoundError("Approval decision")
            proposal = await self.repository.get_proposal(db, decision.proposal_id)
            if proposal is None:
                raise ConflictError("approval_binding_invalid", "Proposal no longer exists")
            thread_id = proposal.workflow_run_id
        async with self._execution_lock(thread_id):
            async with self.database.sessions() as db:
                decision = await db.get(ApprovalDecision, decision_id)
                if decision is None:
                    raise NotFoundError("Approval decision")
                proposal = await self.repository.get_proposal(db, decision.proposal_id)
                if proposal is None:
                    raise ConflictError("approval_binding_invalid", "Proposal no longer exists")
                run = await self.repository.get_run(db, proposal.workflow_run_id)
                if run is None:
                    raise ConflictError("approval_binding_invalid", "Workflow no longer exists")
                if decision.applied_at is not None or run.state in {
                    WorkflowState.COMPLETED,
                    WorkflowState.REJECTED,
                    WorkflowState.INSUFFICIENT,
                    WorkflowState.FAILED,
                }:
                    if decision.applied_at is not None:
                        await self._add_resume_applied_audit(db, run, decision)
                        await db.commit()
                    if run.intent == MCP_DIRECT_WORKFLOW_INTENT:
                        return await self._direct_workflow_state(db, run, decision, proposal)
                    return await self.snapshot(run.id)
                direct_resume = run.intent == MCP_DIRECT_WORKFLOW_INTENT
                replacement = (
                    await self.repository.get_proposal(db, decision.replacement_proposal_id)
                    if decision.replacement_proposal_id is not None
                    else None
                )
                resume = ApprovalResume(
                    decision_id=str(decision.id),
                    decision=decision.decision.value,
                    proposal_id=str(proposal.id),
                    proposal_version=proposal.version,
                    payload_hash=proposal.payload_hash,
                    evidence_snapshot_hash=proposal.evidence_snapshot_hash,
                    replacement_proposal_id=str(replacement.id) if replacement else None,
                    replacement_version=replacement.version if replacement else None,
                    replacement_payload_hash=replacement.payload_hash if replacement else None,
                )
                outbox_event = await db.scalar(
                    select(OutboxEvent).where(OutboxEvent.dedupe_key == f"resume:{decision.id}")
                )
                await self.audits.add(
                    db,
                    actor_id=decision.decided_by_id,
                    action="workflow.resume",
                    resource_type="workflow_run",
                    resource_id=run.id,
                    outcome="started",
                    correlation_id=run.origin_correlation_id,
                    causation_id=str(decision.id),
                    thread_id=run.id,
                    dedupe_key=f"workflow:{run.id}:resume:{decision.id}:started",
                    detail={"outbox_event_id": str(outbox_event.id) if outbox_event else None},
                )
                await db.commit()
            try:
                result: WorkflowGraphState
                if direct_resume:
                    result = await self._resume_direct_decision(thread_id, resume)
                else:
                    command: Command[Any] = Command(resume=resume.model_dump(mode="json"))
                    result = cast(
                        WorkflowGraphState,
                        await self.graph.ainvoke(command, self._config(thread_id)),
                    )
            except ServiceUnavailableError as exc:
                if not isinstance(exc, RetryableServiceUnavailableError) or (
                    terminal_on_transient_failure
                ):
                    await self._record_failure(thread_id, exc)
                raise
            except Exception as exc:
                await self._record_failure(thread_id, exc)
                raise
            async with self.database.sessions() as db:
                run = await self.repository.get_run(db, thread_id)
                if run is not None:
                    await self._add_resume_applied_audit(db, run, decision)
                await db.commit()
            return result

    async def _add_resume_applied_audit(
        self,
        db: AsyncSession,
        run: WorkflowRun,
        decision: ApprovalDecision,
    ) -> None:
        await self.audits.add(
            db,
            actor_id=decision.decided_by_id,
            action="workflow.resume",
            resource_type="workflow_run",
            resource_id=run.id,
            outcome="applied",
            correlation_id=run.origin_correlation_id,
            causation_id=str(decision.id),
            thread_id=run.id,
            dedupe_key=f"workflow:{run.id}:resume:{decision.id}:applied",
            detail={"state": run.state.value},
        )

    async def _resume_direct_decision(
        self, thread_id: uuid.UUID, resume: ApprovalResume
    ) -> WorkflowGraphState:
        decision_id = uuid.UUID(resume.decision_id)
        proposal_id = uuid.UUID(resume.proposal_id)
        async with self.database.sessions() as db:
            decision = await db.get(ApprovalDecision, decision_id)
            proposal = await self.repository.get_proposal(db, proposal_id)
            run = await self.repository.get_run(db, thread_id)
            if decision is None or proposal is None or run is None:
                raise ConflictError(
                    "approval_binding_invalid", "Direct workflow binding is missing"
                )
            if run.intent != MCP_DIRECT_WORKFLOW_INTENT:
                raise ConflictError(
                    "workflow_provenance_invalid", "Direct workflow provenance is invalid"
                )
            if resume.decision == "approve":
                await self.approvals.execute_approved(
                    db,
                    thread_id=thread_id,
                    decision_id=decision_id,
                    proposal_id=proposal_id,
                    proposal_version=resume.proposal_version,
                    payload_hash=resume.payload_hash,
                    evidence_snapshot_hash=resume.evidence_snapshot_hash,
                    correlation_id=run.origin_correlation_id,
                )
            elif resume.decision == "reject":
                await self.approvals.finalize_rejection(
                    db,
                    thread_id=thread_id,
                    decision_id=decision_id,
                    proposal_id=proposal_id,
                )
            else:
                if resume.replacement_proposal_id is None:
                    raise ConflictError(
                        "edit_binding_invalid", "Direct edit replacement binding is missing"
                    )
                await self.approvals.mark_edit_applied(
                    db,
                    thread_id=thread_id,
                    decision_id=decision_id,
                    replacement_proposal_id=uuid.UUID(resume.replacement_proposal_id),
                )
            state = await self._direct_workflow_state(db, run, decision, proposal)
            await db.commit()
            return state

    @staticmethod
    async def _direct_workflow_state(
        db: AsyncSession,
        run: WorkflowRun,
        decision: ApprovalDecision,
        proposal: ActionProposal,
    ) -> WorkflowGraphState:
        actor = await db.get(User, run.requested_by_id)
        if actor is None:
            raise ConflictError("workflow_actor_missing", "Workflow actor no longer exists")
        return {
            "thread_id": str(run.id),
            "actor_id": str(actor.id),
            "actor_role": actor.role.value,
            "question": run.question,
            "document_ids": list(run.document_ids),
            "origin_correlation_id": run.origin_correlation_id,
            "intent": MCP_DIRECT_WORKFLOW_INTENT,
            "action_requested": True,
            "cited_chunk_ids": list(proposal.cited_chunk_ids),
            "proposal_id": str(proposal.id),
            "proposal_version": proposal.version,
            "proposal_payload_hash": proposal.payload_hash,
            "evidence_snapshot_hash": proposal.evidence_snapshot_hash,
            "applied_decision_ids": [str(decision.id)] if decision.applied_at else [],
            "stage_latency_ms": {},
            "tool_trace": ["propose_workflow_task"],
        }

    async def snapshot(self, thread_id: uuid.UUID) -> WorkflowGraphState:
        snapshot = await self.graph.aget_state(self._config(thread_id))
        return cast(WorkflowGraphState, dict(snapshot.values))

    @asynccontextmanager
    async def _execution_lock(self, run_id: uuid.UUID) -> AsyncIterator[None]:
        lock_key = workflow_execution_lock_key(run_id)
        async with self.database.engine.connect() as connection, connection.begin():
            await connection.execute(select(func.pg_advisory_xact_lock(lock_key)))
            yield

    async def _record_failure(self, run_id: uuid.UUID, exc: Exception) -> None:
        code = exc.code if isinstance(exc, AppError) else type(exc).__name__
        detail = exc.message if isinstance(exc, AppError) else "Workflow execution failed"
        async with self.database.sessions() as db:
            run = await self.repository.mark_failed(db, run_id=run_id, code=code, detail=detail)
            if run is not None and run.state == WorkflowState.FAILED:
                await self.audits.add(
                    db,
                    actor_id=None,
                    action="workflow.failed",
                    resource_type="workflow_run",
                    resource_id=run.id,
                    outcome="failed",
                    correlation_id=run.origin_correlation_id,
                    thread_id=run.id,
                    dedupe_key=f"workflow:{run.id}:failed",
                    detail={"error_code": run.error_code},
                )
            await db.commit()

    def _compile(
        self, checkpointer: BaseCheckpointSaver[Any]
    ) -> CompiledStateGraph[WorkflowGraphState, None, WorkflowGraphState, WorkflowGraphState]:
        builder = StateGraph(WorkflowGraphState)
        transient_retry = RetryPolicy(
            max_attempts=2,
            initial_interval=0.5,
            max_interval=2.0,
            retry_on=RetryableServiceUnavailableError,
        )
        builder.add_node("classify", self._classify)
        builder.add_node("retrieve", self._retrieve, retry_policy=transient_retry)
        builder.add_node("sufficiency", self._sufficiency)
        builder.add_node("grounded_response", self._grounded_response, retry_policy=transient_retry)
        builder.add_node("validate", self._validate)
        builder.add_node("persist_analysis", self._persist_analysis)
        builder.add_node("propose_action", self._propose_action)
        builder.add_node("human_review", self._human_review)
        builder.add_node("apply_edit", self._apply_edit)
        builder.add_node("execute_task", self._execute_task)
        builder.add_node("finalize_rejection", self._finalize_rejection)
        builder.add_node("finalize", self._finalize)
        builder.add_edge(START, "classify")
        builder.add_edge("classify", "retrieve")
        builder.add_edge("retrieve", "sufficiency")
        builder.add_edge("sufficiency", "grounded_response")
        builder.add_edge("grounded_response", "validate")
        builder.add_edge("validate", "persist_analysis")
        builder.add_conditional_edges(
            "persist_analysis",
            self._route_after_analysis,
            {"propose": "propose_action", "finalize": "finalize"},
        )
        builder.add_edge("propose_action", "human_review")
        builder.add_conditional_edges(
            "human_review",
            self._route_after_review,
            {
                "approve": "execute_task",
                "reject": "finalize_rejection",
                "edit": "apply_edit",
            },
        )
        builder.add_edge("apply_edit", "human_review")
        builder.add_edge("execute_task", END)
        builder.add_edge("finalize_rejection", END)
        builder.add_edge("finalize", END)
        return builder.compile(checkpointer=checkpointer)

    async def _classify(self, state: WorkflowGraphState) -> dict[str, object]:
        started = time.perf_counter()
        intent, action_requested = _classify_request(state["question"])
        return {
            "intent": intent,
            "action_requested": action_requested,
            "stage_latency_ms": _with_latency(state, "validation", started),
        }

    async def _retrieve(self, state: WorkflowGraphState) -> dict[str, object]:
        started = time.perf_counter()
        document_ids = [uuid.UUID(value) for value in state["document_ids"]]
        async with self.database.sessions() as db:
            result = await self.retriever.search(db, state["question"], document_ids)
        retrieval: list[RetrievalState] = []
        for item in result.chunks:
            marker_ids = list(dict.fromkeys(_MARKER_PATTERN.findall(item.chunk.content)))
            source_match = _SOURCE_PATTERN.search(item.chunk.revision.document.title)
            source_id = (
                marker_ids[0].split(":", maxsplit=1)[0]
                if marker_ids
                else source_match.group(0).upper()
                if source_match
                else None
            )
            retrieval.append(
                {
                    "chunk_id": item.chunk.stable_id,
                    "database_chunk_id": str(item.chunk.id),
                    "source_document_id": str(item.chunk.revision.document_id),
                    "revision_id": str(item.chunk.revision_id),
                    "document_title": item.chunk.revision.document.title,
                    "source_id": source_id,
                    "marker_ids": marker_ids,
                    "anchor_key": item.chunk.anchor.stable_key,
                    "anchor_label": item.chunk.anchor.label,
                    "start_offset": item.chunk.start_offset,
                    "end_offset": item.chunk.end_offset,
                    "content": item.chunk.content,
                    "rrf_score": item.score,
                    "vector_rank": item.vector_rank,
                    "text_rank": item.text_rank,
                    "vector_similarity": item.vector_similarity,
                    "text_score": item.text_score,
                }
            )
        return {
            "retrieval": retrieval,
            "tool_trace": [*state.get("tool_trace", []), "search_documents"],
            "stage_latency_ms": _with_latency(state, "retrieval", started),
        }

    async def _sufficiency(self, state: WorkflowGraphState) -> dict[str, object]:
        started = time.perf_counter()
        retrieval = state.get("retrieval", [])
        top = retrieval[0] if retrieval else None
        absolute = bool(
            top
            and (
                _optional_at_least(
                    top["vector_similarity"], self.settings.retrieval_min_vector_similarity
                )
                or _optional_at_least(top["text_score"], self.settings.retrieval_min_text_score)
            )
        )
        retrieval_sufficient = bool(
            top and top["rrf_score"] >= self.settings.retrieval_min_score and absolute
        )
        qa_context_sufficient = True
        if state.get("intent") == "document_question":
            qa_context_sufficient = (
                assess_qa_context(
                    state["question"],
                    (
                        Evidence(
                            chunk_id=item["chunk_id"],
                            document_title=item["document_title"],
                            anchor_label=item["anchor_label"],
                            content=item["content"],
                            source_id=item["source_id"],
                            marker_ids=tuple(item["marker_ids"]),
                        )
                        for item in retrieval
                    ),
                ).verdict
                is not QAContextVerdict.CLEARLY_ABSENT
            )
        sufficient = retrieval_sufficient and qa_context_sufficient
        return {
            "sufficient": sufficient,
            "stage_latency_ms": _with_latency(state, "validation", started),
        }

    async def _grounded_response(self, state: WorkflowGraphState) -> dict[str, object]:
        started = time.perf_counter()
        if not state.get("sufficient", False):
            output = WorkflowModelOutput(
                answer=INSUFFICIENT_ANSWER,
                insufficient_evidence=True,
            )
        else:
            evidence = [
                Evidence(
                    chunk_id=item["chunk_id"],
                    document_title=item["document_title"],
                    anchor_label=item["anchor_label"],
                    content=item["content"],
                    source_id=item["source_id"],
                    marker_ids=tuple(item["marker_ids"]),
                )
                for item in state.get("retrieval", [])
            ]
            if state.get("intent") == "document_question":
                decision = assess_qa_context(state["question"], evidence)
                if decision.verdict is QAContextVerdict.CLEARLY_ABSENT:
                    output = WorkflowModelOutput(
                        answer=INSUFFICIENT_ANSWER,
                        insufficient_evidence=True,
                    )
                    output = _normalize_workflow_output(output)
                    return {
                        "answer": output.answer,
                        "insufficient_evidence": output.insufficient_evidence,
                        "cited_chunk_ids": [],
                        "cited_marker_ids": [],
                        "claims": [],
                        "findings": [],
                        "proposal_draft": None,
                        "stage_latency_ms": _with_latency(state, "generation", started),
                    }
                if decision.verdict is QAContextVerdict.SUPPORTED:
                    evidence = list(decision.evidence)
                evidence = evidence[:3]
            output = await self.chat.analyze(
                state["question"],
                evidence,
                action_requested=state.get("action_requested", False),
                structured_extraction=state.get("intent") == "structured_extraction",
            )
        output = _normalize_workflow_output(output)
        return {
            "answer": output.answer,
            "insufficient_evidence": output.insufficient_evidence,
            "cited_chunk_ids": list(output.cited_chunk_ids),
            "cited_marker_ids": list(output.cited_marker_ids),
            "claims": [item.model_dump(mode="json") for item in output.claims],
            "findings": [item.model_dump(mode="json") for item in output.findings],
            "proposal_draft": (
                output.proposed_task.model_dump(mode="json")
                if output.proposed_task is not None
                else None
            ),
            "stage_latency_ms": _with_latency(state, "generation", started),
        }

    async def _validate(self, state: WorkflowGraphState) -> dict[str, object]:
        started = time.perf_counter()
        output = WorkflowModelOutput.model_validate(
            {
                "answer": state["answer"],
                "insufficient_evidence": state["insufficient_evidence"],
                "cited_chunk_ids": state.get("cited_chunk_ids", []),
                "cited_marker_ids": state.get("cited_marker_ids", []),
                "claims": state.get("claims", []),
                "findings": state.get("findings", []),
                "proposed_task": state.get("proposal_draft"),
            }
        )
        allowed = {item["chunk_id"] for item in state.get("retrieval", [])}
        referenced = set(output.cited_chunk_ids)
        marker_bindings: list[tuple[set[str], list[str]]] = [
            (set(output.cited_chunk_ids), output.cited_marker_ids)
        ]
        for claim in output.claims:
            referenced.update(claim.cited_chunk_ids)
            marker_bindings.append((set(claim.cited_chunk_ids), claim.cited_marker_ids))
        for finding in output.findings:
            referenced.update(finding.cited_chunk_ids)
            marker_bindings.append((set(finding.cited_chunk_ids), finding.cited_marker_ids))
        if output.proposed_task is not None:
            referenced.update(output.proposed_task.cited_chunk_ids)
            marker_bindings.append(
                (
                    set(output.proposed_task.cited_chunk_ids),
                    output.proposed_task.cited_marker_ids,
                )
            )
        if not referenced.issubset(allowed):
            raise ServiceUnavailableError(
                "model_citation_invalid", "Workflow output cited unavailable evidence"
            )
        marker_ids_by_chunk = {
            item["chunk_id"]: set(item["marker_ids"]) for item in state.get("retrieval", [])
        }
        for chunk_ids, marker_ids in marker_bindings:
            permitted = set().union(
                *(marker_ids_by_chunk.get(chunk_id, set()) for chunk_id in chunk_ids)
            )
            if not set(marker_ids).issubset(permitted):
                raise ServiceUnavailableError(
                    "model_citation_invalid",
                    "Workflow output cited a source marker outside its cited chunks",
                )
        if referenced:
            async with self.database.sessions() as db:
                resolved = await self.resolver.resolve_chunks(db, sorted(referenced))
            if set(resolved) != referenced:
                raise ServiceUnavailableError(
                    "model_citation_invalid", "Workflow citations no longer resolve"
                )
        if state.get("intent") == "document_question" and not output.insufficient_evidence:
            qa_decision = assess_qa_context(
                state["question"],
                (
                    Evidence(
                        chunk_id=item["chunk_id"],
                        document_title=item["document_title"],
                        anchor_label=item["anchor_label"],
                        content=item["content"],
                        source_id=item["source_id"],
                        marker_ids=tuple(
                            marker
                            for marker in item["marker_ids"]
                            if not output.cited_marker_ids or marker in output.cited_marker_ids
                        ),
                    )
                    for item in state.get("retrieval", [])
                    if item["chunk_id"] in output.cited_chunk_ids
                ),
            )
            exact_markers = {marker for _chunk, marker in qa_decision.marker_bindings}
            if qa_decision.verdict is QAContextVerdict.CLEARLY_ABSENT or (
                qa_decision.verdict is QAContextVerdict.SUPPORTED
                and set(output.cited_marker_ids) != exact_markers
            ):
                raise ServiceUnavailableError(
                    "model_grounding_invalid",
                    "Workflow citations do not support the requested subject and answer type",
                )
        try:
            validate_action_claim_grounding(
                output,
                [
                    Evidence(
                        chunk_id=item["chunk_id"],
                        document_title=item["document_title"],
                        anchor_label=item["anchor_label"],
                        content=item["content"],
                        source_id=item["source_id"],
                        marker_ids=tuple(item["marker_ids"]),
                    )
                    for item in state.get("retrieval", [])
                ],
                action_requested=state.get("action_requested", False),
                question=state["question"],
            )
        except ValueError as exc:
            raise ServiceUnavailableError(
                "model_action_invalid", "Workflow output violated the action analysis policy"
            ) from exc
        update: dict[str, object] = {
            "stage_latency_ms": _with_latency(state, "validation", started)
        }
        if referenced:
            update["tool_trace"] = [*state.get("tool_trace", []), "get_document_section"]
        return update

    async def _persist_analysis(self, state: WorkflowGraphState) -> dict[str, object]:
        started = time.perf_counter()
        run_id = uuid.UUID(state["thread_id"])
        claims = [ClaimDraft.model_validate(item) for item in state.get("claims", [])]
        findings = [FindingDraft.model_validate(item) for item in state.get("findings", [])]
        claim_provenance = [
            {
                "origin": claim.origin,
                **(
                    {
                        "normalizer_version": claim.normalizer_version,
                        "source_marker_sha256": claim.source_marker_sha256,
                        "fallback_reason": claim.fallback_reason,
                    }
                    if claim.origin == "deterministic_evidence_normalizer"
                    else {}
                ),
            }
            for claim in claims
        ]
        async with self.database.sessions() as db:
            run = await self.repository.persist_analysis(
                db,
                run_id=run_id,
                intent=state["intent"],
                answer=state["answer"],
                insufficient=state["insufficient_evidence"],
                cited_chunk_ids=state.get("cited_chunk_ids", []),
                findings=findings,
            )
            await self.audits.add(
                db,
                actor_id=uuid.UUID(state["actor_id"]),
                action="workflow.analysis",
                resource_type="workflow_run",
                resource_id=run.id,
                outcome="insufficient" if state["insufficient_evidence"] else "grounded",
                correlation_id=state["origin_correlation_id"],
                thread_id=run.id,
                dedupe_key=f"workflow:{run.id}:analysis:{run.request_hash}",
                detail={
                    "intent": state["intent"],
                    "citation_count": len(state.get("cited_chunk_ids", [])),
                    "claim_count": len(claims),
                    "claim_provenance": claim_provenance,
                    "finding_count": len(findings),
                },
            )
            await db.commit()
        return {"stage_latency_ms": _with_latency(state, "validation", started)}

    async def _propose_action(self, state: WorkflowGraphState) -> dict[str, object]:
        started = time.perf_counter()
        raw_draft = state.get("proposal_draft")
        if raw_draft is None:
            raise ServiceUnavailableError(
                "proposal_missing", "The action request did not produce a valid proposal"
            )
        draft = TaskProposalDraft.model_validate(raw_draft)
        run_id = uuid.UUID(state["thread_id"])
        async with self.database.sessions() as db:
            resolved = await self.resolver.resolve_chunks(db, list(draft.cited_chunk_ids))
            if len(resolved) != len(draft.cited_chunk_ids) or set(resolved) != set(
                draft.cited_chunk_ids
            ):
                raise ServiceUnavailableError(
                    "model_citation_invalid", "Proposal citations no longer resolve"
                )
            evidence_snapshot_hash = compute_evidence_snapshot_hash(
                (chunk_id, chunk.content) for chunk_id, chunk in resolved.items()
            )
            proposal = await self.repository.upsert_proposal(
                db,
                run_id=run_id,
                actor_id=uuid.UUID(state["actor_id"]),
                draft=draft,
                evidence_snapshot_hash=evidence_snapshot_hash,
            )
            await self.audits.add(
                db,
                actor_id=uuid.UUID(state["actor_id"]),
                action="proposal.create",
                resource_type="action_proposal",
                resource_id=proposal.id,
                outcome="pending",
                correlation_id=state["origin_correlation_id"],
                thread_id=run_id,
                dedupe_key=f"workflow:{run_id}:proposal:{proposal.payload_hash}",
                detail={
                    "version": proposal.version,
                    "payload_hash": proposal.payload_hash,
                    "evidence_snapshot_hash": proposal.evidence_snapshot_hash,
                },
            )
            await db.commit()
        return {
            "proposal_id": str(proposal.id),
            "proposal_version": proposal.version,
            "proposal_payload_hash": proposal.payload_hash,
            "evidence_snapshot_hash": proposal.evidence_snapshot_hash,
            "tool_trace": [*state.get("tool_trace", []), "propose_workflow_task"],
            "stage_latency_ms": _with_latency(state, "validation", started),
        }

    async def _human_review(self, state: WorkflowGraphState) -> dict[str, object]:
        resumed = interrupt(_approval_interrupt_payload(state))
        binding = ApprovalResume.model_validate(resumed)
        applied = [*state.get("applied_decision_ids", [])]
        if binding.decision_id not in applied:
            applied.append(binding.decision_id)
        update: dict[str, object] = {
            "resume_decision": binding.model_dump(mode="json"),
            "applied_decision_ids": applied,
        }
        if binding.decision == "edit":
            update.update(
                {
                    "proposal_id": cast(str, binding.replacement_proposal_id),
                    "proposal_version": cast(int, binding.replacement_version),
                    "proposal_payload_hash": cast(str, binding.replacement_payload_hash),
                }
            )
        return update

    async def _apply_edit(self, state: WorkflowGraphState) -> dict[str, object]:
        binding = ApprovalResume.model_validate(state["resume_decision"])
        if binding.replacement_proposal_id is None:
            raise ConflictError("edit_binding_invalid", "Replacement proposal is missing")
        async with self.database.sessions() as db:
            await self.approvals.mark_edit_applied(
                db,
                thread_id=uuid.UUID(state["thread_id"]),
                decision_id=uuid.UUID(binding.decision_id),
                replacement_proposal_id=uuid.UUID(binding.replacement_proposal_id),
            )
            await db.commit()
        return {}

    async def _execute_task(self, state: WorkflowGraphState) -> dict[str, object]:
        started = time.perf_counter()
        binding = ApprovalResume.model_validate(state["resume_decision"])
        async with self.database.sessions() as db:
            task = await self.approvals.execute_approved(
                db,
                thread_id=uuid.UUID(state["thread_id"]),
                decision_id=uuid.UUID(binding.decision_id),
                proposal_id=uuid.UUID(binding.proposal_id),
                proposal_version=binding.proposal_version,
                payload_hash=binding.payload_hash,
                evidence_snapshot_hash=binding.evidence_snapshot_hash,
                correlation_id=state["origin_correlation_id"],
            )
            await db.commit()
        del task
        return {"stage_latency_ms": _with_latency(state, "approval", started)}

    async def _finalize_rejection(self, state: WorkflowGraphState) -> dict[str, object]:
        binding = ApprovalResume.model_validate(state["resume_decision"])
        async with self.database.sessions() as db:
            await self.approvals.finalize_rejection(
                db,
                thread_id=uuid.UUID(state["thread_id"]),
                decision_id=uuid.UUID(binding.decision_id),
                proposal_id=uuid.UUID(binding.proposal_id),
            )
            await db.commit()
        return {}

    async def _finalize(self, state: WorkflowGraphState) -> dict[str, object]:
        run_id = uuid.UUID(state["thread_id"])
        async with self.database.sessions() as db:
            run = await self.repository.get_run(db, run_id, lock=True)
            if run is None:
                raise NotFoundError("Workflow run")
            if not state.get("insufficient_evidence", False):
                run.state = WorkflowState.COMPLETED
            await self.audits.add(
                db,
                actor_id=uuid.UUID(state["actor_id"]),
                action="workflow.finalize",
                resource_type="workflow_run",
                resource_id=run.id,
                outcome=run.state.value,
                correlation_id=state["origin_correlation_id"],
                thread_id=run.id,
                dedupe_key=f"workflow:{run.id}:finalize:{run.state.value}",
            )
            await db.commit()
        return {}

    def _route_after_analysis(self, state: WorkflowGraphState) -> Literal["propose", "finalize"]:
        return "propose" if state.get("proposal_draft") is not None else "finalize"

    def _route_after_review(
        self, state: WorkflowGraphState
    ) -> Literal["approve", "reject", "edit"]:
        binding = ApprovalResume.model_validate(state["resume_decision"])
        return binding.decision

    @staticmethod
    def _config(thread_id: uuid.UUID) -> RunnableConfig:
        return {"configurable": {"thread_id": str(thread_id)}}


def _approval_interrupt_payload(state: WorkflowGraphState) -> dict[str, object]:
    return {
        "type": "approval_required",
        "thread_id": state["thread_id"],
        "proposal_id": state["proposal_id"],
        "proposal_version": state["proposal_version"],
        "payload_hash": state["proposal_payload_hash"],
        "evidence_snapshot_hash": state["evidence_snapshot_hash"],
    }


def _with_latency(state: WorkflowGraphState, stage: str, started: float) -> dict[str, float]:
    latencies = dict(state.get("stage_latency_ms", {}))
    latencies[stage] = latencies.get(stage, 0.0) + (time.perf_counter() - started) * 1000
    return latencies


def _optional_at_least(value: float | None, threshold: float) -> bool:
    return value is not None and value >= threshold


def _is_action_request(normalized_question: str) -> bool:
    return any(term in normalized_question for term in _ACTION_TERMS) or bool(
        _ACTION_PATTERN.search(normalized_question)
    )


def _is_startable_state(state: WorkflowState) -> bool:
    return state == WorkflowState.RUNNING
