"""Runner, capability, gate, and artifact tests."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, cast, get_args

import pytest
from click import unstyle
from localguard_api.evaluation import dataset as evaluation_dataset
from localguard_api.evaluation.cli import app
from localguard_api.evaluation.contracts import (
    Capability,
    EvaluationCase,
    EvaluationInput,
    ForbiddenOutcome,
    ProviderCallDiagnostic,
    ResultStatus,
    RuntimeModelIdentity,
    SystemCaseOutput,
)
from localguard_api.evaluation.dataset import EvaluationDataset, load_dataset
from localguard_api.evaluation.reporting import write_run_artifacts
from localguard_api.evaluation.runner import CaseRunResult, run_evaluation
from localguard_api.models import TaskPriority
from localguard_api.providers import (
    ProviderDiagnosticPhase,
    ProviderFinalReasonCode,
    ProviderValidationHint,
    ProviderValidationStage,
)
from pydantic import ValidationError
from typer.testing import CliRunner

from .factories import perfect_output

pytestmark = pytest.mark.unit


def _literal_values(annotation: Any) -> set[object]:
    arguments = get_args(annotation)
    if not arguments:
        return {annotation}
    values: set[object] = set()
    for argument in arguments:
        if argument is type(None):
            continue
        values.update(_literal_values(argument))
    return values


def test_cli_exposes_the_run_subcommand_used_by_powershell_and_ci() -> None:
    result = CliRunner().invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "--provider" in unstyle(result.output)


def test_repository_root_uses_the_checkout_when_the_package_is_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(__file__).resolve().parents[2]
    installed_module = tmp_path / "lib" / "site-packages" / "localguard_api" / "evaluation"
    monkeypatch.chdir(root)
    monkeypatch.setattr(evaluation_dataset, "__file__", str(installed_module / "dataset.py"))

    assert evaluation_dataset.repository_root() == root


def test_evaluation_script_exposes_explicit_raw_response_capture_switch() -> None:
    script = Path("scripts/evaluate.ps1").read_text(encoding="utf-8")

    assert "[switch]$CaptureRawResponses" in script
    assert "if ($CaptureRawResponses)" in script
    assert "LOCALGUARD_EVAL_CAPTURE_RAW_RESPONSES=1" in script


def test_provider_diagnostic_contract_stays_literal_aligned_with_runtime() -> None:
    assert _literal_values(ProviderCallDiagnostic.model_fields["phase"].annotation) == set(
        get_args(ProviderDiagnosticPhase)
    )
    assert _literal_values(
        ProviderCallDiagnostic.model_fields["validation_stage"].annotation
    ) == set(get_args(ProviderValidationStage))
    assert _literal_values(
        ProviderCallDiagnostic.model_fields["validation_hint"].annotation
    ) == set(get_args(ProviderValidationHint))
    assert _literal_values(
        ProviderCallDiagnostic.model_fields["final_reason_code"].annotation
    ) == set(get_args(ProviderFinalReasonCode))


def test_provider_diagnostic_contract_rejects_incoherent_or_unbound_raw_evidence() -> None:
    with pytest.raises(ValidationError, match="raw provider excerpts require"):
        ProviderCallDiagnostic(
            call_index=1,
            phase="qa_initial",
            http_status=200,
            duration_ms=1.0,
            response_sha256=None,
            validation_stage="schema",
            raw_excerpt="unbound raw output",
        )
    with pytest.raises(ValidationError, match="accepted provider calls cannot"):
        ProviderCallDiagnostic(
            call_index=1,
            phase="qa_initial",
            http_status=200,
            duration_ms=1.0,
            response_sha256="a" * 64,
            validation_stage="accepted",
            final_reason_code="model_schema_invalid",
        )
    with pytest.raises(ValidationError, match="call-bound denials cannot claim"):
        ProviderCallDiagnostic(
            call_index=5,
            phase="workflow_initial",
            http_status=200,
            duration_ms=1.0,
            response_sha256="d" * 64,
            validation_stage="call_bound",
            final_reason_code="evaluation_call_bound_exceeded",
            raw_excerpt="this network call must never happen",
        )


class PerfectSystem:
    def __init__(self, cases: tuple[EvaluationCase, ...]) -> None:
        self._cases = {case.case_id: case for case in cases}
        self.inputs: list[EvaluationInput] = []
        self.closed = False

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset(Capability)

    @property
    def provider_raw_response_capture_enabled(self) -> bool:
        return False

    async def run_case(self, request: EvaluationInput) -> SystemCaseOutput:
        self.inputs.append(request)
        return perfect_output(self._cases[request.case_id])

    async def runtime_identity(self) -> RuntimeModelIdentity:
        return RuntimeModelIdentity(
            provider="deterministic",
            chat_model_name="deterministic-test-chat-v1",
            embedding_model_name="deterministic-test-embedding-v1",
            runtime_version="in-process-v1",
        )

    def drain_provider_diagnostics(self) -> list[ProviderCallDiagnostic]:
        return []

    async def aclose(self) -> None:
        self.closed = True


class DiagnosticSystem(PerfectSystem):
    def __init__(
        self,
        cases: tuple[EvaluationCase, ...],
        *,
        failed_case_id: str | None = None,
    ) -> None:
        super().__init__(cases)
        self.failed_case_id = failed_case_id
        self._pending_diagnostics: list[ProviderCallDiagnostic] = []

    @property
    def provider_raw_response_capture_enabled(self) -> bool:
        return True

    async def run_case(self, request: EvaluationInput) -> SystemCaseOutput:
        self.inputs.append(request)
        if request.case_id == self.failed_case_id:
            self._pending_diagnostics = [
                ProviderCallDiagnostic(
                    call_index=1,
                    phase="workflow_initial",
                    http_status=200,
                    duration_ms=12.5,
                    response_sha256="a" * 64,
                    validation_stage="semantic_grounding",
                    validation_hint="predicate_not_grounded",
                    final_reason_code=None,
                    raw_excerpt="first private raw response",
                ),
                ProviderCallDiagnostic(
                    call_index=2,
                    phase="workflow_repair",
                    http_status=200,
                    duration_ms=8.25,
                    response_sha256="b" * 64,
                    validation_stage="semantic_grounding",
                    validation_hint="normalized_value_not_grounded",
                    final_reason_code="model_schema_invalid",
                    raw_excerpt="second private raw response",
                ),
            ]
            raise RuntimeError("synthetic provider validation failure")
        self._pending_diagnostics = [
            ProviderCallDiagnostic(
                call_index=1,
                phase="qa_initial",
                http_status=200,
                duration_ms=3.5,
                response_sha256="c" * 64,
                validation_stage="accepted",
                validation_hint=None,
                final_reason_code=None,
                raw_excerpt="accepted private raw response",
            )
        ]
        return perfect_output(self._cases[request.case_id])

    def drain_provider_diagnostics(self) -> list[ProviderCallDiagnostic]:
        drained = self._pending_diagnostics
        self._pending_diagnostics = []
        return drained


class EvaluationCallBoundError(RuntimeError):
    code = "evaluation_call_bound_exceeded"


class CallBoundSystem(DiagnosticSystem):
    async def run_case(self, request: EvaluationInput) -> SystemCaseOutput:
        if not self.inputs:
            self.inputs.append(request)
            self._pending_diagnostics = [
                ProviderCallDiagnostic(
                    call_index=index,
                    phase="workflow_initial" if index % 2 else "workflow_repair",
                    http_status=None if index == 5 else 200,
                    duration_ms=0.0 if index == 5 else float(index),
                    response_sha256=None if index == 5 else f"{index}" * 64,
                    validation_stage=("call_bound" if index == 5 else "semantic_grounding"),
                    validation_hint=("predicate_not_grounded" if index < 5 else None),
                    final_reason_code=("evaluation_call_bound_exceeded" if index == 5 else None),
                )
                for index in range(1, 6)
            ]
            raise EvaluationCallBoundError("synthetic call bound")
        return await super().run_case(request)


class NoCapabilitySystem(PerfectSystem):
    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset()


class OneMalformedSystem(PerfectSystem):
    async def run_case(self, request: EvaluationInput) -> SystemCaseOutput:
        self.inputs.append(request)
        if len(self.inputs) == 1:
            return cast(SystemCaseOutput, {"status": "answered"})
        return perfect_output(self._cases[request.case_id])


class InjectionFailureSystem(PerfectSystem):
    async def run_case(self, request: EvaluationInput) -> SystemCaseOutput:
        self.inputs.append(request)
        output = perfect_output(self._cases[request.case_id])
        if request.case_id == "LG-EVAL-INJ-001":
            output.observed_policy_failures = [ForbiddenOutcome.DOCUMENT_INSTRUCTION_FOLLOWED]
        return output


class GroundedPolicyFailureSystem(PerfectSystem):
    async def run_case(self, request: EvaluationInput) -> SystemCaseOutput:
        self.inputs.append(request)
        output = perfect_output(self._cases[request.case_id])
        if request.case_id == "LG-EVAL-GRD-001":
            output.observed_policy_failures = [ForbiddenOutcome.UNSUPPORTED_CLAIM_ASSERTED]
        return output


class OneExecutionFailureSystem(PerfectSystem):
    async def run_case(self, request: EvaluationInput) -> SystemCaseOutput:
        self.inputs.append(request)
        if len(self.inputs) == 1:
            raise RuntimeError("synthetic failure detail\nignored second line")
        return perfect_output(self._cases[request.case_id])


class ConformanceFailureSystem(PerfectSystem):
    async def run_case(self, request: EvaluationInput) -> SystemCaseOutput:
        self.inputs.append(request)
        output = perfect_output(self._cases[request.case_id])
        if request.case_id == "LG-EVAL-GRD-001":
            output.status = ResultStatus.UNANSWERABLE
        if request.case_id == "LG-EVAL-ACT-001":
            output.claims = []
            output.claim_provenance = []
            assert output.proposal is not None
            output.proposal = output.proposal.model_copy(update={"priority": TaskPriority.LOW})
        return SystemCaseOutput.model_validate(output.model_dump(mode="python"))


@pytest.fixture(scope="module")
def dataset() -> EvaluationDataset:
    return load_dataset(verify=False)


@pytest.mark.asyncio
async def test_runner_executes_exactly_25_measured_cases_and_closes_system(
    dataset: EvaluationDataset,
) -> None:
    system = PerfectSystem(dataset.cases)

    run = await run_evaluation(
        dataset,
        system,
        requested_provider="fake",
        runtime_provider="deterministic",
        warmup=False,
    )

    assert len(system.inputs) == 25
    assert [item.case_id for item in run.results] == [case.case_id for case in dataset.cases]
    assert run.aggregate.completed_case_count == 25
    assert run.aggregate.failed_case_count == 0
    assert run.gates.safety_passed
    assert run.gates.quality_passed is None
    assert run.gates.run_passed
    assert run.runtime_model_identity.provider == "deterministic"
    assert not run.provider_raw_response_capture_enabled
    assert run.structured_extraction_mode == "evidence_derived_binding_confirmation_v2"
    assert run.action_proposal_mode == "evidence_derived_binding_selection_v2"
    assert run.claim_provenance.model_claim_count == 0
    assert run.claim_provenance.deterministic_test_provider_claim_count > 0
    assert run.claim_provenance.deterministic_normalizer_claim_count == 0
    assert run.claim_provenance.deterministic_normalizer_case_ids == []
    assert run.claim_provenance.deterministic_normalizer_case_rate == 0.0
    assert run.finding_provenance.model_finding_count == 0
    assert run.finding_provenance.deterministic_test_provider_finding_count > 0
    assert run.finding_provenance.deterministic_normalizer_finding_count == 0
    assert run.finding_provenance.deterministic_normalizer_case_ids == []
    assert run.finding_provenance.deterministic_normalizer_case_rate == 0.0
    assert run.results[0].output is not None
    assert run.results[0].output.stage_latency_ms["total"] == run.results[0].wall_clock_ms
    assert run.results[0].wall_clock_ms >= 0
    assert system.closed


@pytest.mark.asyncio
async def test_provider_label_mismatch_fails_and_closes_system(
    dataset: EvaluationDataset,
) -> None:
    system = PerfectSystem(dataset.cases)

    with pytest.raises(ValueError, match="requested and runtime"):
        await run_evaluation(
            dataset,
            system,
            requested_provider="fake",
            runtime_provider="ollama",
            warmup=False,
        )

    assert system.closed


@pytest.mark.asyncio
async def test_sut_input_excludes_gold_answers_and_expected_state(
    dataset: EvaluationDataset,
) -> None:
    system = PerfectSystem(dataset.cases)

    await run_evaluation(
        dataset,
        system,
        requested_provider="fake",
        runtime_provider="deterministic",
        warmup=False,
    )

    fields = set(EvaluationInput.model_fields)
    assert "expected_status" not in fields
    assert "expected_spans" not in fields
    assert "expected_claims" not in fields
    assert "expected_extractions" not in fields
    assert "expected_tool_trace" not in fields
    assert "expected_proposal" not in fields
    assert system.inputs[20].approval_decisions[0].model_dump() == {
        "step": 1,
        "decision": "approve",
        "patch": {},
    }


@pytest.mark.asyncio
async def test_missing_capabilities_fail_closed_without_invoking_cases(
    dataset: EvaluationDataset,
) -> None:
    system = NoCapabilitySystem(dataset.cases)

    run = await run_evaluation(
        dataset,
        system,
        requested_provider="fake",
        runtime_provider="deterministic",
        warmup=False,
    )

    assert not system.inputs
    assert run.aggregate.completed_case_count == 0
    assert run.aggregate.failed_case_count == 25
    assert run.aggregate.schema_validity.value == 0.0
    assert not run.gates.run_passed
    assert "schema_validity" in run.gates.failed_gates
    assert all(
        item.failure and item.failure.code == "capability_unavailable" for item in run.results
    )
    assert system.closed


@pytest.mark.asyncio
async def test_malformed_system_output_is_visible_and_fails_schema_gate(
    dataset: EvaluationDataset,
) -> None:
    run = await run_evaluation(
        dataset,
        OneMalformedSystem(dataset.cases),
        requested_provider="fake",
        runtime_provider="deterministic",
        warmup=False,
    )

    assert run.aggregate.completed_case_count == 24
    assert run.aggregate.schema_validity.value == 24 / 25
    assert run.results[0].failure is not None
    assert run.results[0].failure.code == "output_schema_invalid"
    assert not run.gates.run_passed


@pytest.mark.asyncio
async def test_execution_failure_includes_bounded_first_line_diagnostics(
    dataset: EvaluationDataset,
) -> None:
    run = await run_evaluation(
        dataset,
        OneExecutionFailureSystem(dataset.cases),
        requested_provider="fake",
        runtime_provider="deterministic",
        warmup=False,
    )

    failure = run.results[0].failure
    assert failure is not None
    assert failure.code == "case_execution_failed"
    assert failure.message == (
        "application case execution failed (RuntimeError): synthetic failure detail"
    )


@pytest.mark.asyncio
async def test_provider_diagnostics_are_attributed_to_success_and_failure_without_leakage(
    dataset: EvaluationDataset,
    tmp_path: Path,
) -> None:
    failed_case_id = dataset.cases[0].case_id
    system = DiagnosticSystem(dataset.cases, failed_case_id=failed_case_id)

    run = await run_evaluation(
        dataset,
        system,
        requested_provider="fake",
        runtime_provider="deterministic",
        warmup=False,
    )

    failed = run.results[0]
    succeeded = run.results[1]
    assert run.provider_raw_response_capture_enabled
    assert failed.failure is not None
    assert [item.call_index for item in failed.provider_diagnostics] == [1, 2]
    assert [item.phase for item in failed.provider_diagnostics] == [
        "workflow_initial",
        "workflow_repair",
    ]
    assert failed.provider_diagnostics[-1].final_reason_code == "model_schema_invalid"
    assert [item.call_index for item in succeeded.provider_diagnostics] == [1]
    assert succeeded.provider_diagnostics[0].validation_stage == "accepted"

    malformed = succeeded.model_dump(mode="python")
    malformed["provider_diagnostics"][0]["call_index"] = 2
    with pytest.raises(ValidationError, match="indexes must be contiguous"):
        CaseRunResult.model_validate(malformed)

    artifacts = write_run_artifacts(run, tmp_path / "results")
    markdown = artifacts.markdown.read_text(encoding="utf-8")
    assert "## Provider call diagnostics" in markdown
    assert f"`{failed_case_id}` | 1 | `workflow_initial`" in markdown
    assert f"`{failed_case_id}` | 2 | `workflow_repair`" in markdown
    assert "`model_schema_invalid`" in markdown
    assert "Raw provider response capture: `enabled`" in markdown
    assert "first private raw response" not in markdown
    assert "second private raw response" not in markdown
    raw_payload = json.loads(artifacts.raw_json.read_text(encoding="utf-8"))
    assert raw_payload["results"][0]["provider_diagnostics"][1]["raw_excerpt"] == (
        "second private raw response"
    )
    raw_payload["provider_raw_response_capture_enabled"] = False
    with pytest.raises(ValidationError, match="enabled capture attestation"):
        type(run).model_validate(raw_payload)


@pytest.mark.asyncio
async def test_warmup_diagnostics_are_drained_before_measured_cases(
    dataset: EvaluationDataset,
) -> None:
    system = DiagnosticSystem(dataset.cases)

    run = await run_evaluation(
        dataset,
        system,
        requested_provider="fake",
        runtime_provider="deterministic",
        warmup=True,
    )

    assert run.warmup_completed
    assert len(system.inputs) == 26
    assert all(
        [item.call_index for item in result.provider_diagnostics] == [1] for result in run.results
    )


@pytest.mark.asyncio
async def test_fifth_provider_call_is_preserved_as_an_explicit_case_failure(
    dataset: EvaluationDataset,
) -> None:
    run = await run_evaluation(
        dataset,
        CallBoundSystem(dataset.cases),
        requested_provider="fake",
        runtime_provider="deterministic",
        warmup=False,
    )

    first = run.results[0]
    assert first.failure is not None
    assert first.failure.code == "provider_call_bound_exceeded"
    assert [item.call_index for item in first.provider_diagnostics] == [1, 2, 3, 4, 5]
    assert first.provider_diagnostics[-1].validation_stage == "call_bound"
    assert first.provider_diagnostics[-1].final_reason_code == "evaluation_call_bound_exceeded"
    assert first.provider_diagnostics[-1].http_status is None
    assert first.provider_diagnostics[-1].response_sha256 is None
    assert first.provider_diagnostics[-1].raw_excerpt is None
    assert first.provider_diagnostics[-1].duration_ms == 0.0
    assert run.results[1].provider_diagnostics[0].call_index == 1

    mixed_family = first.model_dump(mode="python")
    mixed_family["provider_diagnostics"][1]["phase"] = "qa_repair"
    with pytest.raises(ValidationError, match="cannot mix request families"):
        CaseRunResult.model_validate(mixed_family)

    repair_first = first.model_dump(mode="python")
    repair_first["provider_diagnostics"][0]["phase"] = "workflow_repair"
    with pytest.raises(ValidationError, match="must start with an initial phase"):
        CaseRunResult.model_validate(repair_first)

    repair_denial = first.model_dump(mode="python")
    repair_denial["provider_diagnostics"][4]["phase"] = "workflow_repair"
    with pytest.raises(ValidationError, match="must start a new graph attempt"):
        CaseRunResult.model_validate(repair_denial)

    premature_denial = first.model_dump(mode="python")
    premature_denial["provider_diagnostics"] = [
        {**premature_denial["provider_diagnostics"][4], "call_index": 1}
    ]
    with pytest.raises(ValidationError, match="only the denied fifth"):
        CaseRunResult.model_validate(premature_denial)


@pytest.mark.asyncio
async def test_injection_policy_failure_forces_nonzero_gate_result(
    dataset: EvaluationDataset,
) -> None:
    run = await run_evaluation(
        dataset,
        InjectionFailureSystem(dataset.cases),
        requested_provider="fake",
        runtime_provider="deterministic",
        warmup=False,
    )

    assert run.aggregate.injection_policy_compliance.value is not None
    assert run.aggregate.injection_policy_compliance.value < 1.0
    assert "injection_policy_compliance" in run.gates.failed_gates
    assert not run.gates.run_passed


@pytest.mark.asyncio
async def test_any_declared_forbidden_outcome_forces_nonzero_safety_gate(
    dataset: EvaluationDataset,
) -> None:
    run = await run_evaluation(
        dataset,
        GroundedPolicyFailureSystem(dataset.cases),
        requested_provider="fake",
        runtime_provider="deterministic",
        warmup=False,
    )

    assert run.aggregate.injection_policy_compliance.value == 1.0
    assert run.aggregate.forbidden_outcome_compliance.value is not None
    assert run.aggregate.forbidden_outcome_compliance.value < 1.0
    assert "forbidden_outcome_compliance" in run.gates.failed_gates
    assert not run.gates.safety_passed
    assert not run.gates.run_passed


@pytest.mark.asyncio
async def test_completed_but_semantically_wrong_outputs_fail_conformance_gates(
    dataset: EvaluationDataset,
) -> None:
    run = await run_evaluation(
        dataset,
        ConformanceFailureSystem(dataset.cases),
        requested_provider="fake",
        runtime_provider="deterministic",
        warmup=False,
    )

    assert run.aggregate.completed_case_count == 25
    assert run.gates.safety_passed
    assert run.gates.quality_passed is None
    assert not run.gates.run_passed
    assert {"status_accuracy", "proposal_exact_match", "missing_expected_claim_count"} <= set(
        run.gates.failed_gates
    )


@pytest.mark.asyncio
async def test_report_artifacts_reconcile_to_raw_json_hash(
    dataset: EvaluationDataset,
    tmp_path: Path,
) -> None:
    run = await run_evaluation(
        dataset,
        PerfectSystem(dataset.cases),
        requested_provider="fake",
        runtime_provider="deterministic",
        warmup=False,
    )

    artifacts = write_run_artifacts(run, tmp_path / "results")

    raw_bytes = artifacts.raw_json.read_bytes()
    summary = json.loads(artifacts.summary_json.read_text(encoding="utf-8"))
    assert summary["raw_result_sha256"] == hashlib.sha256(raw_bytes).hexdigest()
    assert summary["structured_extraction_mode"] == "evidence_derived_binding_confirmation_v2"
    assert summary["action_proposal_mode"] == "evidence_derived_binding_selection_v2"
    assert artifacts.latest_json.read_bytes() == artifacts.summary_json.read_bytes()
    assert artifacts.latest_markdown.read_bytes() == artifacts.markdown.read_bytes()
    if os.name != "nt":
        assert all(
            stat.S_IMODE(path.stat().st_mode) == 0o644
            for path in (
                artifacts.raw_json,
                artifacts.summary_json,
                artifacts.markdown,
                artifacts.latest_json,
                artifacts.latest_markdown,
            )
        )
    markdown = artifacts.markdown.read_text(encoding="utf-8")
    assert "Result schema: `1.2.0`" in markdown
    assert "Cases completed: 25/25" in markdown
    assert "Quality gates: NOT APPLICABLE (deterministic provider)" in markdown
    assert "Overall run: PASS" in markdown
    assert "Raw provider response capture: `disabled`" in markdown
    assert f"Corpus bundle SHA-256: `{dataset.corpus_bundle_sha256}`" in markdown
    assert "Deterministic evidence-normalizer claims" in markdown
    assert "The model confirms that whole set or abstains" in markdown
    assert "Deterministic-test-provider findings" in markdown
    assert "Deterministic-test-provider finding cases: `LG-EVAL-GRD-007`" in markdown
    assert "Deterministic evidence-normalizer findings" in markdown
    assert "Deterministic evidence-normalizer finding cases: none" in markdown
    assert "Action proposal provenance" in markdown
    assert "No provider chat calls were recorded for this run." in markdown
    assert "not presented as a real-model quality benchmark" in markdown


def test_dataset_loader_uses_versioned_raw_case_hash(dataset: EvaluationDataset) -> None:
    expected = hashlib.sha256(Path("evals/dataset/cases.jsonl").read_bytes()).hexdigest()

    assert dataset.version == "1.0.2"
    assert dataset.sha256 == expected
    assert dataset.cases_sha256 == expected
    assert len(dataset.canonical_manifest_sha256) == 64
    assert len(dataset.generated_fixture_manifest_sha256) == 64
    assert len(dataset.corpus_bundle_sha256) == 64
    assert len(dataset.cases) == 25
