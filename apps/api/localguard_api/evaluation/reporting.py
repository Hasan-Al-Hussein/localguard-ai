"""Atomic JSON and Markdown artifacts generated only from measured run data."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .contracts import FindingOrigin, RuntimeModelIdentity, StrictModel
from .metrics import AggregateMetrics
from .runner import ClaimProvenanceSummary, EvaluationRun, FindingProvenanceSummary, GateStatus


class EvaluationSummary(StrictModel):
    schema_version: str
    run_id: str
    dataset_version: str
    dataset_sha256: str
    cases_sha256: str
    canonical_manifest_sha256: str
    generated_fixture_manifest_sha256: str
    corpus_bundle_sha256: str
    requested_provider: Literal["fake", "ollama"]
    runtime_provider: Literal["deterministic", "ollama"]
    provider_raw_response_capture_enabled: bool
    runtime_model_identity: RuntimeModelIdentity
    structured_extraction_mode: Literal["evidence_derived_binding_confirmation_v2"]
    action_proposal_mode: Literal["evidence_derived_binding_selection_v2"]
    raw_result_sha256: str
    aggregate: AggregateMetrics
    claim_provenance: ClaimProvenanceSummary
    finding_provenance: FindingProvenanceSummary
    gates: GateStatus


@dataclass(frozen=True, slots=True)
class WrittenArtifacts:
    run_directory: Path
    raw_json: Path
    summary_json: Path
    markdown: Path
    latest_json: Path
    latest_markdown: Path


def write_run_artifacts(run: EvaluationRun, output_root: Path) -> WrittenArtifacts:
    output_root.mkdir(parents=True, exist_ok=True)
    run_directory = output_root / run.run_id
    try:
        run_directory.mkdir(parents=False, exist_ok=False)
    except FileExistsError as exc:
        raise RuntimeError(f"evaluation run directory already exists: {run.run_id}") from exc

    raw_payload = _json_bytes(run.model_dump(mode="json"))
    raw_hash = hashlib.sha256(raw_payload).hexdigest()
    summary = EvaluationSummary(
        schema_version=run.schema_version,
        run_id=run.run_id,
        dataset_version=run.dataset_version,
        dataset_sha256=run.dataset_sha256,
        cases_sha256=run.cases_sha256,
        canonical_manifest_sha256=run.canonical_manifest_sha256,
        generated_fixture_manifest_sha256=run.generated_fixture_manifest_sha256,
        corpus_bundle_sha256=run.corpus_bundle_sha256,
        requested_provider=run.requested_provider,
        runtime_provider=run.runtime_provider,
        provider_raw_response_capture_enabled=run.provider_raw_response_capture_enabled,
        runtime_model_identity=run.runtime_model_identity,
        structured_extraction_mode=run.structured_extraction_mode,
        action_proposal_mode=run.action_proposal_mode,
        raw_result_sha256=raw_hash,
        aggregate=run.aggregate,
        claim_provenance=run.claim_provenance,
        finding_provenance=run.finding_provenance,
        gates=run.gates,
    )
    summary_payload = _json_bytes(summary.model_dump(mode="json"))
    markdown_payload = render_markdown(run, raw_hash).encode("utf-8")

    raw_json = run_directory / "run.json"
    summary_json = run_directory / "summary.json"
    markdown = run_directory / "report.md"
    latest_json = output_root / "latest.json"
    latest_markdown = output_root / "latest.md"
    _atomic_write(raw_json, raw_payload)
    _atomic_write(summary_json, summary_payload)
    _atomic_write(markdown, markdown_payload)
    _atomic_write(latest_json, summary_payload)
    _atomic_write(latest_markdown, markdown_payload)
    return WrittenArtifacts(
        run_directory=run_directory,
        raw_json=raw_json,
        summary_json=summary_json,
        markdown=markdown,
        latest_json=latest_json,
        latest_markdown=latest_markdown,
    )


def render_markdown(run: EvaluationRun, raw_result_sha256: str) -> str:
    aggregate = run.aggregate
    recall = aggregate.grounded_retrieval.macro_recall_at_k
    total_latency = aggregate.latency_by_stage.get("total")
    failed_cases = [item for item in run.results if item.failure is not None]
    triggered_cases = [
        item
        for item in run.results
        if item.metrics is not None and item.metrics.policy.triggered_forbidden_outcomes
    ]
    diagnostic_rows = [
        (result.case_id, diagnostic)
        for result in run.results
        for diagnostic in result.provider_diagnostics
    ]
    test_provider_finding_case_ids = [
        result.case_id
        for result in run.results
        if result.output is not None
        and any(
            finding.origin is FindingOrigin.DETERMINISTIC_TEST_PROVIDER
            for finding in result.output.extractions
        )
    ]
    lines = [
        "# LocalGuard evaluation report",
        "",
        f"- Result schema: `{run.schema_version}`",
        f"- Run: `{run.run_id}`",
        f"- Dataset: `{run.dataset_version}` (`{run.dataset_sha256}`)",
        f"- Cases SHA-256: `{run.cases_sha256}`",
        f"- Canonical source manifest SHA-256: `{run.canonical_manifest_sha256}`",
        (f"- Generated fixture manifest SHA-256: `{run.generated_fixture_manifest_sha256}`"),
        f"- Corpus bundle SHA-256: `{run.corpus_bundle_sha256}`",
        f"- Requested provider: `{run.requested_provider}`",
        f"- Runtime provider: `{run.runtime_provider}`",
        (
            "- Raw provider response capture: "
            f"`{'enabled' if run.provider_raw_response_capture_enabled else 'disabled'}`"
        ),
        (
            "- Chat model: "
            f"`{run.runtime_model_identity.chat_model_name}` "
            f"(`{run.runtime_model_identity.chat_model_digest or 'not-applicable'}`)"
        ),
        (
            "- Embedding model: "
            f"`{run.runtime_model_identity.embedding_model_name}` "
            f"(`{run.runtime_model_identity.embedding_model_digest or 'not-applicable'}`)"
        ),
        f"- Runtime version: `{run.runtime_model_identity.runtime_version}`",
        f"- Structured extraction mode: `{run.structured_extraction_mode}`",
        f"- Action proposal mode: `{run.action_proposal_mode}`",
        (
            "- Structured extraction provenance: the application deterministically parses and "
            "request-scopes the complete bounded set of exact evidence bindings. The model "
            "confirms that whole set or abstains; the application derives the actor, finding "
            "type, action, deadline, summary, and fixed nonfactual answer from each uniquely "
            "resolved confirmed marker."
        ),
        (
            "- Action proposal provenance: the model selects one exact allowlisted evidence "
            "binding. The application deterministically derives the normalized claim and inert "
            "proposal from that uniquely resolved marker and a syntactically bound trusted "
            "request date or timestamp; execution still requires explicit approval."
        ),
        f"- Raw result SHA-256: `{raw_result_sha256}`",
        f"- Cases completed: {aggregate.completed_case_count}/{aggregate.case_count}",
        f"- Safety gates: {'PASS' if run.gates.safety_passed else 'FAIL'}",
        f"- Quality gates: {_quality_label(run.gates.quality_passed)}",
        f"- Overall run: {'PASS' if run.gates.run_passed else 'FAIL'}",
        "",
        "## Measured metrics",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Expected-status accuracy | {_format_metric(aggregate.status_accuracy.value)} |",
        f"| Grounded retrieval recall@1 (macro) | {_format_metric(recall.get('1'))} |",
        f"| Grounded retrieval recall@3 (macro) | {_format_metric(recall.get('3'))} |",
        f"| Grounded retrieval recall@5 (macro) | {_format_metric(recall.get('5'))} |",
        (
            "| Citation precision (macro, missing citations score zero) | "
            f"{_format_metric(aggregate.citation_precision_macro)} |"
        ),
        (
            "| Citation precision (pooled returned citations) | "
            f"{_format_metric(aggregate.citation_precision.value)} |"
        ),
        f"| Answer cases with zero citations | {aggregate.zero_citation_answer_count} |",
        f"| Extraction precision | {_format_metric(aggregate.extraction.precision)} |",
        f"| Extraction recall | {_format_metric(aggregate.extraction.recall)} |",
        f"| Extraction F1 | {_format_metric(aggregate.extraction.f1)} |",
        f"| Unsupported-claim rate | {_format_metric(aggregate.unsupported_claim_rate.value)} |",
        f"| Grounding score | {_format_metric(aggregate.grounding_score)} |",
        f"| Missing expected structured claims | {aggregate.missing_expected_claim_count} |",
        f"| Model-authored structured claims | {run.claim_provenance.model_claim_count} |",
        (
            "| Deterministic-test-provider structured claims | "
            f"{run.claim_provenance.deterministic_test_provider_claim_count} |"
        ),
        (
            "| Deterministic evidence-normalizer claims | "
            f"{run.claim_provenance.deterministic_normalizer_claim_count} |"
        ),
        (
            "| Deterministic evidence-normalizer case rate | "
            f"{run.claim_provenance.deterministic_normalizer_case_rate:.4f} |"
        ),
        (
            "| Exact tool-sequence accuracy | "
            f"{_format_metric(aggregate.tool_selection_accuracy.value)} |"
        ),
        f"| Exact proposal match | {_format_metric(aggregate.proposal_exact_match.value)} |",
        (
            "| Approval-gate compliance | "
            f"{_format_metric(aggregate.approval_gate_compliance.value)} |"
        ),
        (
            "| Approval-transition coverage | "
            f"{_format_metric(aggregate.approval_transition_coverage.value)} |"
        ),
        (
            "| Observed forbidden-outcome compliance | "
            f"{_format_metric(aggregate.forbidden_outcome_compliance.value)} |"
        ),
        (
            "| Forbidden-outcome control coverage | "
            f"{_format_metric(aggregate.forbidden_outcome_control_coverage.value)} |"
        ),
        (
            "| Injection policy compliance | "
            f"{_format_metric(aggregate.injection_policy_compliance.value)} |"
        ),
        (
            "| Insufficient-evidence abstention | "
            f"{_format_metric(aggregate.insufficient_abstention.value)} |"
        ),
        (
            "| Total latency p50 | "
            f"{_format_latency(total_latency.p50_ms if total_latency else None)} |"
        ),
        (
            "| Total latency p95 | "
            f"{_format_latency(total_latency.p95_ms if total_latency else None)} |"
        ),
        f"| Pre-approval executions | {aggregate.pre_approval_execution_count} |",
        "",
        "## Claim provenance",
        "",
        (
            "Deterministic evidence-normalizer cases: "
            + (
                ", ".join(
                    f"`{item}`" for item in run.claim_provenance.deterministic_normalizer_case_ids
                )
                if run.claim_provenance.deterministic_normalizer_case_ids
                else "none"
            )
        ),
        "",
        "## Finding provenance",
        "",
        (
            "Deterministic-test-provider findings: "
            f"{run.finding_provenance.deterministic_test_provider_finding_count}/"
            f"{run.finding_provenance.total_finding_count}"
        ),
        (
            "Deterministic-test-provider finding cases: "
            + (
                ", ".join(f"`{item}`" for item in test_provider_finding_case_ids)
                if test_provider_finding_case_ids
                else "none"
            )
        ),
        (
            "Deterministic evidence-normalizer findings: "
            f"{run.finding_provenance.deterministic_normalizer_finding_count}/"
            f"{run.finding_provenance.total_finding_count}"
        ),
        (
            "Deterministic evidence-normalizer finding cases: "
            + (
                ", ".join(
                    f"`{item}`" for item in run.finding_provenance.deterministic_normalizer_case_ids
                )
                if run.finding_provenance.deterministic_normalizer_case_ids
                else "none"
            )
        ),
        "",
        "## Provider call diagnostics",
        "",
        (
            "Raw model text is excluded from this Markdown report. Response hashes, bounded "
            "validation stages, and fixed reason codes are retained below."
        ),
        "",
    ]
    if diagnostic_rows:
        lines.extend(
            [
                "| Case | Call | Phase | HTTP | Duration | Validation stage | Hint | "
                "Final reason | Response SHA-256 |",
                "|---|---:|---|---:|---:|---|---|---|---|",
            ]
        )
        lines.extend(
            (
                f"| `{case_id}` | {diagnostic.call_index} | `{diagnostic.phase}` | "
                f"{diagnostic.http_status if diagnostic.http_status is not None else 'n/a'} | "
                f"{diagnostic.duration_ms:.2f} ms | `{diagnostic.validation_stage}` | "
                f"`{diagnostic.validation_hint or 'none'}` | "
                f"`{diagnostic.final_reason_code or 'none'}` | "
                f"`{diagnostic.response_sha256 or 'none'}` |"
            )
            for case_id, diagnostic in diagnostic_rows
        )
        lines.append("")
    else:
        lines.extend(["No provider chat calls were recorded for this run.", ""])
    lines.extend(
        [
            "## Failures",
            "",
        ]
    )
    if not failed_cases and not triggered_cases and not run.gates.failed_gates:
        lines.append("No execution, policy, or gate failures were recorded.")
        lines.append("")
    else:
        if run.gates.failed_gates:
            lines.append(
                "Failed gates: " + ", ".join(f"`{item}`" for item in run.gates.failed_gates)
            )
            lines.append("")
        if failed_cases:
            lines.extend(["| Case | Failure | Detail |", "|---|---|---|"])
            lines.extend(
                (
                    f"| `{item.case_id}` | `{item.failure.code}` | "
                    f"{_markdown_cell(item.failure.message)} |"
                )
                for item in failed_cases
                if item.failure is not None
            )
            lines.append("")
        if triggered_cases:
            lines.extend(["| Case | Triggered forbidden outcomes |", "|---|---|"])
            lines.extend(
                "| `"
                + item.case_id
                + "` | "
                + ", ".join(
                    f"`{outcome.value}`"
                    for outcome in (
                        item.metrics.policy.triggered_forbidden_outcomes
                        if item.metrics is not None
                        else []
                    )
                )
                + " |"
                for item in triggered_cases
            )
            lines.append("")
    lines.extend(
        [
            "## Interpretation",
            "",
            "These values were computed from the raw per-case application outputs in this run. "
            "No paid or learned LLM judge was used. A deterministic-provider run proves the test "
            "path and safety invariants; it is not presented as a real-model quality benchmark.",
            "",
        ]
    )
    return "\n".join(lines)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _format_metric(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _format_latency(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f} ms"


def _quality_label(value: bool | None) -> str:
    if value is None:
        return "NOT APPLICABLE (deterministic provider)"
    return "PASS" if value else "FAIL"


def _markdown_cell(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")
