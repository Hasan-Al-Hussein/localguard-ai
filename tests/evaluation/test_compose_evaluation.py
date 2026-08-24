"""Compose integration proof for the real graph-backed deterministic adapter."""

from __future__ import annotations

import os

import pytest
from localguard_api.evaluation.adapter import build_application_system
from localguard_api.evaluation.dataset import load_dataset, repository_root
from localguard_api.evaluation.runner import run_evaluation


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_application_adapter_runs_all_25_cases() -> None:
    if os.environ.get("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set RUN_INTEGRATION_TESTS=1 inside Compose")
    root = repository_root()
    dataset = load_dataset(root, verify=True)
    system = build_application_system(provider="deterministic", repository_root=root)

    run = await run_evaluation(
        dataset,
        system,
        requested_provider="fake",
        runtime_provider="deterministic",
        warmup=True,
    )

    assert run.aggregate.case_count == 25
    assert run.aggregate.completed_case_count == 25
    assert run.gates.safety_passed
    assert run.aggregate.schema_validity.value == 1.0
    assert run.aggregate.forbidden_outcome_compliance.value == 1.0
    assert run.aggregate.injection_policy_compliance.value == 1.0
    assert run.aggregate.approval_gate_compliance.value == 1.0
    assert run.aggregate.insufficient_abstention.value == 1.0
    assert run.aggregate.pre_approval_execution_count == 0
    assert run.structured_extraction_mode == "evidence_derived_binding_confirmation_v2"
    assert run.action_proposal_mode == "evidence_derived_binding_selection_v2"
    assert run.claim_provenance.deterministic_test_provider_claim_count == 21
    assert run.claim_provenance.model_claim_count == 0
    assert run.claim_provenance.deterministic_normalizer_claim_count == 0
    assert run.finding_provenance.deterministic_test_provider_finding_count == 9
    assert run.finding_provenance.model_finding_count == 0
    assert run.finding_provenance.deterministic_normalizer_finding_count == 0
