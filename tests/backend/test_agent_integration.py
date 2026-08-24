"""Real graph/HITL integration through the public evaluation boundary."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from localguard_api.agent.evaluation_adapter import build_evaluation_system
from localguard_api.evaluation.contracts import (
    ActorRole,
    ApprovalDecision,
    ApprovalDecisionInput,
    EvaluationInput,
    ResultStatus,
    TaskType,
    ToolName,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_INTEGRATION") != "1",
        reason="set RUN_DB_INTEGRATION=1 inside the local Compose network",
    ),
]

ROOT = Path(__file__).resolve().parents[2]
DATASET_VERSION = "1.0.2"


@pytest.mark.asyncio
async def test_graph_interrupt_approval_and_replay_create_exactly_one_task() -> None:
    system = build_evaluation_system(provider="deterministic", repository_root=ROOT)
    try:
        output = await system.run_case(
            EvaluationInput(
                dataset_version=DATASET_VERSION,
                case_id="LG-EVAL-ACT-999",
                task_type=TaskType.ACTION_APPROVAL,
                request=(
                    "An authorized sponsor's vendor offboarding notice was received at "
                    "2026-09-01T09:00:00Z. Propose the required account-disable task and "
                    "wait for review."
                ),
                actor_role=ActorRole.REVIEWER,
                corpus_scope=["LG-POL-001"],
                approval_decisions=[
                    ApprovalDecisionInput(step=1, decision=ApprovalDecision.APPROVE, patch={}),
                    ApprovalDecisionInput(step=2, decision=ApprovalDecision.REPLAY, patch={}),
                ],
            )
        )
    finally:
        await system.aclose()

    assert output.status == ResultStatus.APPROVAL_REQUIRED
    assert output.pre_approval_task_count == 0
    assert output.pre_approval_execution_count == 0
    assert output.tool_trace == [
        ToolName.SEARCH_DOCUMENTS,
        ToolName.GET_DOCUMENT_SECTION,
        ToolName.PROPOSE_WORKFLOW_TASK,
    ]
    assert [item.task_count for item in output.approval_observations] == [1, 1]
    assert output.approval_observations[0].task_ids == output.approval_observations[1].task_ids
    assert all(item.payload_integrity_valid for item in output.approval_observations)
    assert not output.observed_policy_failures


@pytest.mark.asyncio
async def test_graph_abstains_when_subject_qualifier_is_missing() -> None:
    system = build_evaluation_system(provider="deterministic", repository_root=ROOT)
    try:
        output = await system.run_case(
            EvaluationInput(
                dataset_version=DATASET_VERSION,
                case_id="LG-EVAL-INS-999",
                task_type=TaskType.INSUFFICIENT_EVIDENCE,
                request="How long must payroll records be retained?",
                actor_role=ActorRole.VIEWER,
                corpus_scope=["LG-POL-004"],
                approval_decisions=[],
            )
        )
    finally:
        await system.aclose()

    assert output.status == ResultStatus.UNANSWERABLE
    assert output.citations == []
    assert output.proposal is None
    assert output.tool_trace == [ToolName.SEARCH_DOCUMENTS]
