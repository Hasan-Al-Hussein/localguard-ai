"""Real PostgreSQL regressions for workflow state and approval integrity."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import timedelta
from pathlib import Path
from typing import cast

import httpx
import pytest
from localguard_api.agent.contracts import FindingDraft, WorkflowModelOutput
from localguard_api.agent.evaluation_adapter import (
    ApplicationEvaluationSystem,
    build_evaluation_system,
)
from localguard_api.agent.persistence import ProposalBinding, expire_pending_proposals
from localguard_api.dispatch import OutboxRepository
from localguard_api.errors import (
    ConflictError,
    RetryableServiceUnavailableError,
    ServiceUnavailableError,
)
from localguard_api.evaluation.contracts import (
    ActorRole,
    ApprovalDecisionInput,
    EvaluationInput,
    TaskType,
)
from localguard_api.evaluation.contracts import (
    ApprovalDecision as EvaluationDecision,
)
from localguard_api.main import create_app
from localguard_api.models import (
    ActionProposal,
    ApprovalDecision,
    AuditEvent,
    DecisionKind,
    Document,
    ExtractedFinding,
    FindingType,
    OutboxEvent,
    OutboxState,
    ProposalState,
    Role,
    SessionToken,
    User,
    WorkflowRun,
    WorkflowState,
    WorkflowTask,
    utc_now,
)
from localguard_api.providers import ChatProvider, Evidence, GeneratedAnswer
from localguard_api.security import hash_password
from sqlalchemy import delete, func, select, text

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_INTEGRATION") != "1",
        reason="set RUN_DB_INTEGRATION=1 inside the local Compose network",
    ),
]

ROOT = Path(__file__).resolve().parents[2]
DATASET_VERSION = "1.0.2"
_ACTION_REQUEST = (
    "An authorized sponsor's vendor offboarding notice was received at "
    "2026-08-20T09:00:00Z. "
    "Propose the required account-disable task and wait for review."
)
_SUPPORTED_QA_REQUEST = "How long after notice must the vendor account be disabled?"


def _system() -> ApplicationEvaluationSystem:
    return cast(
        ApplicationEvaluationSystem,
        build_evaluation_system(provider="deterministic", repository_root=ROOT),
    )


def _action_input(*decisions: ApprovalDecisionInput) -> EvaluationInput:
    return EvaluationInput(
        dataset_version=DATASET_VERSION,
        case_id="LG-EVAL-ACT-998",
        task_type=TaskType.ACTION_APPROVAL,
        request=_ACTION_REQUEST,
        actor_role=ActorRole.REVIEWER,
        corpus_scope=["LG-POL-001"],
        approval_decisions=list(decisions),
    )


async def _pending_proposal(
    system: ApplicationEvaluationSystem,
) -> tuple[uuid.UUID, ActionProposal, User]:
    output = await system.run_case(_action_input())
    async with system.database.sessions() as db:
        proposal = await db.scalar(
            select(ActionProposal).where(ActionProposal.workflow_run_id == output.trace_id)
        )
        reviewer = await db.scalar(
            select(User).where(User.role == Role.REVIEWER, User.is_active.is_(True))
        )
    assert proposal is not None
    assert reviewer is not None
    return output.trace_id, proposal, reviewer


async def _approve(
    system: ApplicationEvaluationSystem, proposal: ActionProposal, reviewer: User
) -> uuid.UUID:
    async with system.database.sessions() as db:
        outcome = await system.approvals.decide(
            db,
            proposal_id=proposal.id,
            actor=reviewer,
            decision=DecisionKind.APPROVE,
            binding=ProposalBinding(
                version=proposal.version,
                payload_hash=proposal.payload_hash,
                evidence_snapshot_hash=proposal.evidence_snapshot_hash,
            ),
            correlation_id="approval-integrity-regression",
        )
        await db.commit()
        return outcome.decision.id


@pytest.mark.asyncio
async def test_structured_finding_provenance_survives_process_restart_and_api_read() -> None:
    system = _system()
    run_id: uuid.UUID | None = None
    api_user_id = uuid.uuid4()
    api_username = f"finding-api-{uuid.uuid4().hex}"
    api_password = "finding persistence integration password"
    marker_id = "LG-POL-001:L010"
    marker_hash = "f" * 64

    class EvidenceFindingChat:
        model_name = "evidence-finding-persistence"

        async def answer(self, _question: str, _evidence: list[Evidence]) -> GeneratedAnswer:
            raise AssertionError("structured workflow must not call answer")

        async def analyze(
            self,
            _question: str,
            evidence: list[Evidence],
            *,
            action_requested: bool,
            structured_extraction: bool = False,
        ) -> WorkflowModelOutput:
            assert structured_extraction and not action_requested
            selected = next(item for item in evidence if marker_id in item.marker_ids)
            return WorkflowModelOutput(
                answer="Structured findings extracted.",
                cited_chunk_ids=[selected.chunk_id],
                cited_marker_ids=[marker_id],
                insufficient_evidence=False,
                findings=[
                    FindingDraft(
                        finding_type=FindingType.OBLIGATION,
                        summary="disable vendor account",
                        normalized_value="1_hour_after_offboarding_notice_received",
                        responsible_party="Service Desk",
                        cited_chunk_ids=[selected.chunk_id],
                        cited_marker_ids=[marker_id],
                        fields={
                            "actor": "Service Desk",
                            "action": "disable vendor account",
                            "deadline": "1_hour_after_offboarding_notice_received",
                        },
                        origin="deterministic_evidence_normalizer",
                        normalizer_version="structured-obligation-binding-v2",
                        source_marker_sha256=marker_hash,
                        derivation_reason="evidence_binding_confirmed",
                    )
                ],
            )

    settings = system.settings
    try:
        document_ids = await system._ensure_documents(["LG-POL-001"])
        actor = await system._get_actor(Role.REVIEWER)
        async with system.database.sessions() as db:
            run = await system.repository.create_run(
                db,
                actor=actor,
                question=(
                    "Extract the responsible parties, required actions, and deadlines "
                    "for vendor offboarding."
                ),
                document_ids=document_ids,
                correlation_id="finding-persistence-regression",
            )
            db.add(
                User(
                    id=api_user_id,
                    username=api_username,
                    display_name="Finding API Reader",
                    password_hash=hash_password(api_password),
                    role=Role.REVIEWER,
                )
            )
            await db.commit()
            run_id = run.id
        system.orchestrator.chat = cast(ChatProvider, EvidenceFindingChat())
        await system.orchestrator.start(run_id)
    finally:
        await system.aclose()

    assert run_id is not None
    app = create_app(settings)
    try:
        # The evaluation graph used an in-memory checkpointer. A new app instance has no
        # access to that graph state, so this read proves the public fields came from PostgreSQL.
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://localhost",
            ) as client,
        ):
            login = await client.post(
                "/auth/login",
                json={"username": api_username, "password": api_password},
            )
            assert login.status_code == 200, login.text
            response = await client.get(
                "/findings",
                params={"workflow_run_id": str(run_id)},
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload["total"] == 1
            finding = payload["items"][0]
            assert finding["fields"] == {
                "actor": "Service Desk",
                "action": "disable vendor account",
                "deadline": "1_hour_after_offboarding_notice_received",
            }
            assert finding["responsible_party"] == "Service Desk"
            assert finding["normalized_value"] == ("1_hour_after_offboarding_notice_received")
            assert finding["cited_marker_ids"] == [marker_id]
            assert finding["origin"] == "deterministic_evidence_normalizer"
            assert finding["normalizer_version"] == "structured-obligation-binding-v2"
            assert finding["source_marker_sha256"] == marker_hash
            assert finding["derivation_reason"] == "evidence_binding_confirmed"
            assert finding["evidence"][0]["available"] is True
    finally:
        async with app.state.database.sessions() as db:
            if run_id is not None:
                await db.execute(
                    delete(ExtractedFinding).where(ExtractedFinding.workflow_run_id == run_id)
                )
                await db.execute(delete(WorkflowRun).where(WorkflowRun.id == run_id))
            await db.execute(delete(SessionToken).where(SessionToken.user_id == api_user_id))
            await db.execute(delete(AuditEvent).where(AuditEvent.actor_id == api_user_id))
            await db.execute(delete(User).where(User.id == api_user_id))
            await db.commit()
        await app.state.database.close()


@pytest.mark.asyncio
async def test_duplicate_start_after_completed_execution_is_a_terminal_noop() -> None:
    system = _system()
    try:
        output = await system.run_case(
            _action_input(
                ApprovalDecisionInput(
                    step=1,
                    decision=EvaluationDecision.APPROVE,
                    patch={},
                )
            )
        )
        await system.orchestrator.start(output.trace_id)
        await system.orchestrator.start(output.trace_id)
        async with system.database.sessions() as db:
            run = await db.get(WorkflowRun, output.trace_id)
            proposal_count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(ActionProposal)
                    .where(ActionProposal.workflow_run_id == output.trace_id)
                )
                or 0
            )
            task_count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(WorkflowTask)
                    .join(ActionProposal, ActionProposal.id == WorkflowTask.proposal_id)
                    .where(ActionProposal.workflow_run_id == output.trace_id)
                )
                or 0
            )
        assert run is not None and run.state == WorkflowState.COMPLETED
        assert proposal_count == 1
        assert task_count == 1
    finally:
        await system.aclose()


@pytest.mark.asyncio
async def test_terminal_graph_resume_recreates_missing_applied_audit() -> None:
    system = _system()
    try:
        output = await system.run_case(
            _action_input(
                ApprovalDecisionInput(
                    step=1,
                    decision=EvaluationDecision.APPROVE,
                    patch={},
                )
            )
        )
        async with system.database.sessions() as db:
            decision = await db.scalar(
                select(ApprovalDecision)
                .join(ActionProposal, ActionProposal.id == ApprovalDecision.proposal_id)
                .where(ActionProposal.workflow_run_id == output.trace_id)
            )
            assert decision is not None and decision.applied_at is not None
            await db.execute(
                delete(AuditEvent).where(
                    AuditEvent.thread_id == output.trace_id,
                    AuditEvent.action == "workflow.resume",
                    AuditEvent.outcome == "applied",
                )
            )
            await db.commit()

        replay = await system.orchestrator.resume_decision(decision.id)
        assert replay["thread_id"] == str(output.trace_id)
        async with system.database.sessions() as db:
            audit_count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.thread_id == output.trace_id,
                        AuditEvent.action == "workflow.resume",
                        AuditEvent.outcome == "applied",
                    )
                )
                or 0
            )
            task_count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(WorkflowTask)
                    .join(ActionProposal, ActionProposal.id == WorkflowTask.proposal_id)
                    .where(ActionProposal.workflow_run_id == output.trace_id)
                )
                or 0
            )
        assert audit_count == 1
        assert task_count == 1
    finally:
        await system.aclose()


@pytest.mark.asyncio
async def test_concurrent_duplicate_start_creates_one_waiting_proposal() -> None:
    system = _system()
    try:
        document_ids = await system._ensure_documents(["LG-POL-001"])
        actor = await system._get_actor(Role.REVIEWER)
        async with system.database.sessions() as db:
            run = await system.repository.create_run(
                db,
                actor=actor,
                question=_ACTION_REQUEST,
                document_ids=document_ids,
                correlation_id="concurrent-start",
            )
            await db.commit()
        await asyncio.gather(
            system.orchestrator.start(run.id),
            system.orchestrator.start(run.id),
        )
        async with system.database.sessions() as db:
            persisted = await db.get(WorkflowRun, run.id)
            proposal_count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(ActionProposal)
                    .where(ActionProposal.workflow_run_id == run.id)
                )
                or 0
            )
        assert persisted is not None and persisted.state == WorkflowState.WAITING_APPROVAL
        assert proposal_count == 1
    finally:
        await system.aclose()


@pytest.mark.asyncio
async def test_pending_lists_lazily_expire_stale_proposals_with_audit() -> None:
    system = _system()
    try:
        run_id, proposal, reviewer = await _pending_proposal(system)
        async with system.database.sessions() as db:
            mutable = await db.get(ActionProposal, proposal.id, with_for_update=True)
            assert mutable is not None
            mutable.expires_at = utc_now() - timedelta(seconds=1)
            await db.commit()

        async with system.database.sessions() as db:
            expired = await expire_pending_proposals(
                db,
                correlation_id="lazy-expiry-regression",
                actor_id=reviewer.id,
            )
            pending, _pending_total = await system.repository.list_proposals(
                db,
                states=[ProposalState.PENDING],
                offset=0,
                limit=100,
            )
            await db.commit()
        assert expired == 1
        assert proposal.id not in {item.id for item in pending}

        async with system.database.sessions() as db:
            persisted = await db.get(ActionProposal, proposal.id)
            run = await db.get(WorkflowRun, run_id)
            audit_count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.resource_id == proposal.id,
                        AuditEvent.action == "proposal.expire",
                        AuditEvent.outcome == "expired",
                    )
                )
                or 0
            )
        assert persisted is not None and persisted.state == ProposalState.EXPIRED
        assert run is not None and run.state == WorkflowState.FAILED
        assert run.error_code == "proposal_expired"
        assert audit_count == 1
    finally:
        await system.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["canonical", "denormalized", "both"])
async def test_post_approval_payload_mutation_fails_closed(mutation: str) -> None:
    system = _system()
    try:
        run_id, proposal, reviewer = await _pending_proposal(system)
        decision_id = await _approve(system, proposal, reviewer)
        async with system.database.sessions() as db:
            mutable = await db.get(ActionProposal, proposal.id, with_for_update=True)
            assert mutable is not None
            if mutation in {"canonical", "both"}:
                mutable.canonical_payload = {
                    **mutable.canonical_payload,
                    "title": "MUTATED AFTER HUMAN APPROVAL",
                }
            if mutation in {"denormalized", "both"}:
                mutable.title = "MUTATED AFTER HUMAN APPROVAL"
            await db.commit()
        with pytest.raises(ConflictError) as captured:
            await system.orchestrator.resume_decision(decision_id)
        assert captured.value.code == "proposal_payload_invalid"
        async with system.database.sessions() as db:
            run = await db.get(WorkflowRun, run_id)
            persisted = await db.get(ActionProposal, proposal.id)
            task_count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(WorkflowTask)
                    .where(WorkflowTask.proposal_id == proposal.id)
                )
                or 0
            )
        assert run is not None and run.state == WorkflowState.FAILED
        assert persisted is not None and persisted.state == ProposalState.FAILED
        assert task_count == 0
    finally:
        await system.aclose()


@pytest.mark.asyncio
async def test_deleted_approved_evidence_blocks_task_and_purges_checkpoints() -> None:
    system = _system()
    marker = "LG-POL-001:L004 PRIVATE CHECKPOINT MARKER"
    try:
        run_id, proposal, reviewer = await _pending_proposal(system)
        decision_id = await _approve(system, proposal, reviewer)
        async with system.database.sessions() as db:
            run = await db.get(WorkflowRun, run_id)
            assert run is not None and run.document_ids
            document_id = uuid.UUID(run.document_ids[0])
            await db.execute(
                text(
                    "INSERT INTO checkpoints "
                    "(thread_id, checkpoint_ns, checkpoint_id, type, checkpoint, metadata) "
                    "VALUES (:thread_id, '', :checkpoint_id, 'json', "
                    "CAST(:checkpoint AS jsonb), '{}'::jsonb)"
                ),
                {
                    "thread_id": str(run_id),
                    "checkpoint_id": uuid.uuid4().hex,
                    "checkpoint": '{"private":"' + marker + '"}',
                },
            )
            await db.commit()
        async with system.database.sessions() as db:
            await system.documents.soft_delete(db, document_id, reviewer)
            await db.commit()
        async with system.database.sessions() as db:
            checkpoint_count = int(
                await db.scalar(
                    text("SELECT count(*) FROM checkpoints WHERE thread_id = :thread_id"),
                    {"thread_id": str(run_id)},
                )
                or 0
            )
            document = await db.get(Document, document_id)
        assert checkpoint_count == 0
        assert document is not None and document.deleted_at is not None

        with pytest.raises(ConflictError) as captured:
            await system.orchestrator.resume_decision(decision_id)
        assert captured.value.code == "approval_evidence_invalid"
        async with system.database.sessions() as db:
            task_count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(WorkflowTask)
                    .where(WorkflowTask.proposal_id == proposal.id)
                )
                or 0
            )
            run = await db.get(WorkflowRun, run_id)
        assert task_count == 0
        assert run is not None and run.state == WorkflowState.FAILED
    finally:
        await system.aclose()


@pytest.mark.asyncio
async def test_persistent_graph_failure_is_visible_but_transient_attempt_is_not_terminal() -> None:
    system = _system()

    class FailingChat:
        model_name = "persistent-failure"

        def __init__(self) -> None:
            self.calls = 0

        async def answer(self, *_args: object, **_kwargs: object) -> object:
            raise RetryableServiceUnavailableError(
                "generation_transport_failed", "Local generation failed"
            )

        async def analyze(self, *_args: object, **_kwargs: object) -> object:
            self.calls += 1
            raise RetryableServiceUnavailableError(
                "generation_transport_failed", "Local generation failed"
            )

    try:
        document_ids = await system._ensure_documents(["LG-POL-001"])
        actor = await system._get_actor(Role.VIEWER)
        async with system.database.sessions() as db:
            run = await system.repository.create_run(
                db,
                actor=actor,
                question=_SUPPORTED_QA_REQUEST,
                document_ids=document_ids,
                correlation_id="failure-boundary",
            )
            await db.commit()
        failing_chat = FailingChat()
        system.orchestrator.chat = cast(ChatProvider, failing_chat)
        with pytest.raises(ServiceUnavailableError):
            await system.orchestrator.start(run.id, terminal_on_transient_failure=False)
        assert failing_chat.calls == 2
        async with system.database.sessions() as db:
            after_transient = await db.get(WorkflowRun, run.id)
        assert after_transient is not None and after_transient.state == WorkflowState.RUNNING

        with pytest.raises(ServiceUnavailableError):
            await system.orchestrator.start(run.id, terminal_on_transient_failure=True)
        assert failing_chat.calls == 4
        async with system.database.sessions() as db:
            failed = await db.get(WorkflowRun, run.id)
            audit_count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.thread_id == run.id,
                        AuditEvent.action == "workflow.failed",
                    )
                )
                or 0
            )
        assert failed is not None and failed.state == WorkflowState.FAILED
        assert failed.error_code == "generation_transport_failed"
        assert audit_count == 1
    finally:
        await system.aclose()


@pytest.mark.asyncio
async def test_permanent_model_failure_is_not_graph_retried_and_allows_outbox_ack() -> None:
    system = _system()
    outbox = OutboxRepository()

    class InvalidChat:
        model_name = "permanent-invalid-output"

        def __init__(self) -> None:
            self.calls = 0

        async def answer(self, *_args: object, **_kwargs: object) -> object:
            raise ServiceUnavailableError(
                "model_schema_invalid", "The local model returned invalid output"
            )

        async def analyze(self, *_args: object, **_kwargs: object) -> object:
            self.calls += 1
            raise ServiceUnavailableError(
                "model_schema_invalid", "The local model returned invalid output"
            )

    try:
        document_ids = await system._ensure_documents(["LG-POL-001"])
        actor = await system._get_actor(Role.VIEWER)
        async with system.database.sessions() as db:
            run = await system.repository.create_run(
                db,
                actor=actor,
                question=_SUPPORTED_QA_REQUEST,
                document_ids=document_ids,
                correlation_id="permanent-model-failure",
            )
            event = await outbox.add(
                db,
                topic="localguard.run_workflow",
                aggregate_type="workflow_run",
                aggregate_id=run.id,
                dedupe_key=f"permanent-model:{run.id}",
                args=[str(run.id)],
                origin_correlation_id=run.origin_correlation_id,
            )
            await db.commit()
        async with system.database.sessions() as db:
            await outbox.mark_dispatched(
                db,
                event.id,
                str(event.id),
                delivery_timeout_seconds=system.settings.outbox_delivery_timeout_seconds,
            )
            await db.commit()

        invalid_chat = InvalidChat()
        system.orchestrator.chat = cast(ChatProvider, invalid_chat)
        with pytest.raises(ServiceUnavailableError) as captured:
            await system.orchestrator.start(run.id, terminal_on_transient_failure=False)
        assert captured.value.code == "model_schema_invalid"
        assert invalid_chat.calls == 1

        async with system.database.sessions() as db:
            persisted = await db.get(WorkflowRun, run.id)
            failed_audit = await db.scalar(
                select(AuditEvent).where(
                    AuditEvent.thread_id == run.id,
                    AuditEvent.action == "workflow.failed",
                    AuditEvent.outcome == "failed",
                )
            )
            acknowledged = await outbox.acknowledge_if_complete(db, event.id)
            await db.commit()
            persisted_event = await db.get(OutboxEvent, event.id)
        assert persisted is not None and persisted.state == WorkflowState.FAILED
        assert persisted.error_code == "model_schema_invalid"
        assert failed_audit is not None
        assert acknowledged
        assert persisted_event is not None
        assert persisted_event.state == OutboxState.ACKNOWLEDGED
    finally:
        await system.aclose()


@pytest.mark.asyncio
async def test_inactive_actor_preflight_fails_run_and_allows_outbox_ack() -> None:
    system = _system()
    outbox = OutboxRepository()
    actor_id: uuid.UUID | None = None
    try:
        document_ids = await system._ensure_documents(["LG-POL-001"])
        actor = await system._get_actor(Role.VIEWER)
        actor_id = actor.id
        async with system.database.sessions() as db:
            run = await system.repository.create_run(
                db,
                actor=actor,
                question=_SUPPORTED_QA_REQUEST,
                document_ids=document_ids,
                correlation_id="inactive-actor-preflight",
            )
            event = await outbox.add(
                db,
                topic="localguard.run_workflow",
                aggregate_type="workflow_run",
                aggregate_id=run.id,
                dedupe_key=f"inactive-actor:{run.id}",
                args=[str(run.id)],
                origin_correlation_id=run.origin_correlation_id,
            )
            await db.commit()
        async with system.database.sessions() as db:
            await outbox.mark_dispatched(
                db,
                event.id,
                str(event.id),
                delivery_timeout_seconds=system.settings.outbox_delivery_timeout_seconds,
            )
            inactive = await db.get(User, actor.id, with_for_update=True)
            assert inactive is not None
            inactive.is_active = False
            await db.commit()

        with pytest.raises(ConflictError) as captured:
            await system.orchestrator.start(run.id)
        assert captured.value.code == "workflow_actor_inactive"

        async with system.database.sessions() as db:
            persisted = await db.get(WorkflowRun, run.id)
            failed_audit = await db.scalar(
                select(AuditEvent).where(
                    AuditEvent.thread_id == run.id,
                    AuditEvent.action == "workflow.failed",
                    AuditEvent.outcome == "failed",
                )
            )
            assert await outbox.acknowledge_if_complete(db, event.id)
            await db.commit()
            persisted_event = await db.get(OutboxEvent, event.id)
        assert persisted is not None and persisted.state == WorkflowState.FAILED
        assert persisted.error_code == "workflow_actor_inactive"
        assert failed_audit is not None
        assert persisted_event is not None
        assert persisted_event.state == OutboxState.ACKNOWLEDGED
    finally:
        if actor_id is not None:
            async with system.database.sessions() as db:
                restored = await db.get(User, actor_id, with_for_update=True)
                if restored is not None:
                    restored.is_active = True
                await db.commit()
        await system.aclose()
