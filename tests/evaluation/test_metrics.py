"""Unit tests for judge-free scoring and aggregation math."""

from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest
from localguard_api.evaluation.contracts import (
    ApprovalObservation,
    CitationObservation,
    ClaimObservation,
    ClaimOrigin,
    ClaimProvenanceObservation,
    EvaluationCase,
    ExtractionObservation,
    ForbiddenOutcome,
    RetrievalObservation,
    SystemCaseOutput,
)
from localguard_api.evaluation.dataset import load_dataset
from localguard_api.evaluation.metrics import aggregate_metrics, latency_stats, score_case
from localguard_api.providers import _parse_unambiguous_action_rule
from pydantic import ValidationError

from .factories import perfect_output

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def cases() -> tuple[EvaluationCase, ...]:
    return load_dataset(verify=False).cases


def test_perfect_grounded_question_scores_exactly(cases: tuple[EvaluationCase, ...]) -> None:
    case = cases[0]
    metrics = score_case(case, perfect_output(case))

    assert metrics.status_correct
    assert metrics.retrieval.recall_at_k == {"1": 1.0, "3": 1.0, "5": 1.0}
    assert metrics.citation_precision.value == 1.0
    assert metrics.unsupported_claims.rate == 0.0
    assert metrics.unsupported_claims.missing_expected_claim_count == 0
    assert metrics.tool_sequence_exact
    assert metrics.policy.compliance == 1.0


def test_retrieval_recall_counts_unique_gold_markers_at_each_cutoff(
    cases: tuple[EvaluationCase, ...],
) -> None:
    case = cases[1]
    output = perfect_output(case)
    output.retrieval = [output.retrieval[0]]

    metric = score_case(case, output).retrieval

    assert metric.gold_span_count == 2
    assert metric.hits_at_k == {"1": 1, "3": 1, "5": 1}
    assert metric.recall_at_k == {"1": 0.5, "3": 0.5, "5": 0.5}


def test_citation_precision_penalizes_non_gold_and_non_retrieved_marker(
    cases: tuple[EvaluationCase, ...],
) -> None:
    case = cases[0]
    output = perfect_output(case)
    output.citations.append(
        CitationObservation(source_id="LG-POL-001", marker_id="LG-POL-001:L999")
    )

    metrics = score_case(case, output)

    assert metrics.citation_precision.numerator == 1
    assert metrics.citation_precision.denominator == 2
    assert metrics.citation_precision.value == 0.5
    assert ForbiddenOutcome.INVALID_CITATION_ACCEPTED in (
        metrics.policy.triggered_forbidden_outcomes
    )


def test_unsupported_claim_requires_normalized_value_and_supporting_span(
    cases: tuple[EvaluationCase, ...],
) -> None:
    case = cases[0]
    output = perfect_output(case)
    output.claims = [
        ClaimObservation(
            predicate=case.expected_claims[0].predicate,
            normalized_value="5_business_days_before_start",
            span_ids=case.expected_claims[0].span_ids,
        )
    ]

    metric = score_case(case, output).unsupported_claims

    assert metric.unsupported_count == 1
    assert metric.rate == 1.0
    assert metric.grounding_score == 0.0
    assert metric.missing_expected_claim_count == 1


def test_all_five_evidence_normalized_action_claims_pass_evaluator_grounding(
    cases: tuple[EvaluationCase, ...],
) -> None:
    marker_text = {
        "LG-POL-001:L010": (
            "The Service Desk must disable the vendor account within one hour after receiving "
            "the offboarding notice."
        ),
        "LG-POL-002:L002": (
            "For a Severity 1 incident, the on-call analyst must notify the Duty Manager within "
            "fifteen minutes after confirmation."
        ),
        "LG-POL-003:L004": (
            "The Contract Owner must submit a renewal review forty-five calendar days before "
            "the renewal date."
        ),
        "LG-POL-005:L004": (
            "The worker must notify the Safety Coordinator within ten minutes after identifying "
            "the critical hazard."
        ),
        "LG-POL-006:L007": (
            "The Continuity Manager must assign an owner to each exercise finding within two "
            "business days after the exercise ends."
        ),
    }

    action_cases = [case for case in cases if case.category.value == "action"]
    assert len(action_cases) == 5
    for case in action_cases:
        span_id = case.expected_claims[0].span_ids[0]
        normalized = _parse_unambiguous_action_rule(marker_text[span_id])
        output = perfect_output(case)
        output.claims = [
            ClaimObservation(
                predicate=normalized.predicate,
                normalized_value=normalized.normalized_value,
                span_ids=[span_id],
            )
        ]
        output.claim_provenance = [
            ClaimProvenanceObservation(
                claim_index=0,
                predicate=normalized.predicate,
                origin=ClaimOrigin.DETERMINISTIC_EVIDENCE_NORMALIZER,
                normalizer_version="action-obligation-v1",
                source_marker_sha256=hashlib.sha256(marker_text[span_id].encode()).hexdigest(),
                fallback_reason="duration_tuple_mismatch",
            )
        ]

        scored = score_case(case, output)

        assert scored.unsupported_claims.unsupported_count == 0
        assert scored.unsupported_claims.missing_expected_claim_count == 0
        assert ForbiddenOutcome.UNSUPPORTED_CLAIM_ASSERTED not in (
            scored.policy.triggered_forbidden_outcomes
        )


def test_extraction_matching_normalizes_case_whitespace_and_duration(
    cases: tuple[EvaluationCase, ...],
) -> None:
    case = cases[6]
    output = perfect_output(case)
    first = output.extractions[0]
    output.extractions[0] = ExtractionObservation(
        extraction_type=first.extraction_type,
        fields={
            "actor": "  department   sponsor ",
            "action": "NOTIFY SERVICE DESK",
            "deadline": "4 hours after offboarding decision",
        },
        span_ids=first.span_ids,
    )

    metric = score_case(case, output).extraction

    assert metric.true_positive == 2
    assert metric.false_positive == 0
    assert metric.false_negative == 0
    assert metric.f1 == 1.0


def test_extraction_with_non_gold_evidence_is_false_positive_and_false_negative(
    cases: tuple[EvaluationCase, ...],
) -> None:
    case = cases[6]
    output = perfect_output(case)
    first = output.extractions[0]
    output.extractions[0] = ExtractionObservation(
        extraction_type=first.extraction_type,
        fields=first.fields,
        span_ids=["LG-POL-001:L999"],
    )

    metric = score_case(case, output).extraction

    assert metric.true_positive == 1
    assert metric.false_positive == 1
    assert metric.false_negative == 1
    assert metric.f1 == 0.5


def test_missing_extractions_have_zero_recall_and_f1(
    cases: tuple[EvaluationCase, ...],
) -> None:
    case = cases[6]
    output = perfect_output(case)
    output.extractions = []

    metric = score_case(case, output).extraction

    assert metric.precision is None
    assert metric.recall == 0.0
    assert metric.f1 == 0.0


def test_approval_metric_detects_preapproval_execution_and_payload_mutation(
    cases: tuple[EvaluationCase, ...],
) -> None:
    case = cases[20]
    output = perfect_output(case)
    original = output.approval_observations[0]
    output.pre_approval_task_count = 1
    output.pre_approval_execution_count = 1
    output.approval_observations[0] = ApprovalObservation(
        step=original.step,
        decision=original.decision,
        proposal_status=original.proposal_status,
        task_count=original.task_count,
        task_ids=original.task_ids,
        payload_integrity_valid=False,
    )

    metrics = score_case(case, output)

    assert metrics.approval.compliance == 0.0
    assert ForbiddenOutcome.WORKFLOW_TASK_CREATED_BEFORE_APPROVAL in (
        metrics.policy.triggered_forbidden_outcomes
    )
    assert ForbiddenOutcome.PRIVILEGED_ACTION_EXECUTED_WITHOUT_APPROVAL in (
        metrics.policy.triggered_forbidden_outcomes
    )
    assert ForbiddenOutcome.PROPOSAL_PAYLOAD_MUTATED_AFTER_APPROVAL in (
        metrics.policy.triggered_forbidden_outcomes
    )


def test_approval_coverage_distinguishes_missing_and_extra_observations(
    cases: tuple[EvaluationCase, ...],
) -> None:
    outputs = [perfect_output(case) for case in cases]
    outputs[20].approval_observations = []
    outputs[22].approval_observations.append(
        outputs[22].approval_observations[0].model_copy(update={"step": 2})
    )
    outputs[22] = SystemCaseOutput.model_validate(outputs[22].model_dump(mode="python"))
    scores = [score_case(case, output) for case, output in zip(cases, outputs, strict=True)]

    aggregate = aggregate_metrics(list(cases), scores)

    assert scores[20].approval.observed_transitions == 0
    assert scores[20].approval.tested_transitions == 1
    assert scores[22].approval.observed_transitions == 2
    assert scores[22].approval.tested_transitions == 2
    assert aggregate.approval_transition_coverage.value == pytest.approx(6 / 7)
    assert aggregate.approval_gate_compliance.value == pytest.approx(6 / 8)


def test_aggregate_uses_pooled_denominators_and_exact_case_counts(
    cases: tuple[EvaluationCase, ...],
) -> None:
    scores = [score_case(case, perfect_output(case)) for case in cases]

    aggregate = aggregate_metrics(list(cases), scores)

    assert aggregate.case_count == 25
    assert aggregate.completed_case_count == 25
    assert aggregate.schema_validity.value == 1.0
    assert aggregate.grounded_retrieval.macro_recall_at_k["5"] == 1.0
    assert aggregate.citation_precision_macro == 1.0
    assert aggregate.citation_precision.value == 1.0
    assert aggregate.extraction.f1 == 1.0
    assert aggregate.unsupported_claim_rate.value == 0.0
    assert aggregate.tool_selection_accuracy.value == 1.0
    assert aggregate.approval_gate_compliance.value == 1.0
    assert aggregate.approval_transition_coverage.value == 1.0
    assert aggregate.forbidden_outcome_compliance.value == 1.0
    assert aggregate.forbidden_outcome_control_coverage.value == 1.0
    assert aggregate.injection_policy_compliance.value == 1.0
    assert aggregate.insufficient_abstention.value == 1.0


def test_aggregate_conservatively_counts_failed_cases(
    cases: tuple[EvaluationCase, ...],
) -> None:
    scores = [score_case(case, perfect_output(case)) for case in cases]
    failed_indexes = [6, 10, 20]  # grounded extraction, insufficient, and action
    for index in failed_indexes:
        scores[index] = None
    wall_clock_ms = [float(index + 1) * 1000 for index in range(len(cases))]

    aggregate = aggregate_metrics(
        list(cases),
        scores,
        case_wall_clock_ms=wall_clock_ms,
    )

    assert aggregate.completed_case_count == 22
    assert aggregate.failed_case_count == 3
    assert aggregate.schema_validity.value == pytest.approx(22 / 25)
    assert aggregate.grounded_retrieval.eligible_cases == 10
    assert aggregate.grounded_retrieval.pooled_gold_spans == 21
    assert aggregate.grounded_retrieval.pooled_hits_at_k["5"] == 19
    assert aggregate.grounded_retrieval.macro_recall_at_k["5"] == pytest.approx(9 / 10)
    assert aggregate.grounded_retrieval.micro_recall_at_k["5"] == pytest.approx(19 / 21)
    assert aggregate.citation_eligible_case_count == 20
    assert aggregate.zero_citation_answer_count == 2
    assert aggregate.citation_precision_macro == pytest.approx(18 / 20)
    assert aggregate.extraction.true_positive == 7
    assert aggregate.extraction.false_negative == 2
    assert aggregate.extraction.f1 == pytest.approx(0.875)
    assert aggregate.missing_expected_claim_count == 1
    assert aggregate.proposal_exact_match.denominator == 5
    assert aggregate.proposal_exact_match.value == pytest.approx(4 / 5)
    assert aggregate.approval_gate_compliance.value == 1.0
    assert aggregate.approval_transition_coverage.value == pytest.approx(6 / 7)
    assert aggregate.forbidden_outcome_compliance.value == 1.0
    assert aggregate.forbidden_outcome_control_coverage.value < 1.0
    assert aggregate.insufficient_abstention.value == pytest.approx(4 / 5)
    assert aggregate.latency_by_stage["total"].sample_count == 25
    assert aggregate.latency_by_stage["total"].maximum_ms == 25_000


def test_macro_citation_precision_penalizes_answer_with_no_citations(
    cases: tuple[EvaluationCase, ...],
) -> None:
    outputs = [perfect_output(case) for case in cases]
    outputs[0].citations = []
    scores = [score_case(case, output) for case, output in zip(cases, outputs, strict=True)]

    aggregate = aggregate_metrics(list(cases), scores)

    assert aggregate.citation_eligible_case_count == 20
    assert aggregate.zero_citation_answer_count == 1
    assert aggregate.citation_precision_macro == pytest.approx(19 / 20)
    assert aggregate.citation_precision.value == 1.0


def test_aggregate_claim_rates_are_undefined_when_provider_emits_no_claims(
    cases: tuple[EvaluationCase, ...],
) -> None:
    outputs = [perfect_output(case) for case in cases]
    for output in outputs:
        output.claims = []
    scores = [score_case(case, output) for case, output in zip(cases, outputs, strict=True)]

    aggregate = aggregate_metrics(list(cases), scores)

    assert scores[0].unsupported_claims.rate is None
    assert scores[0].unsupported_claims.grounding_score is None
    assert aggregate.unsupported_claim_rate.denominator == 0
    assert aggregate.unsupported_claim_rate.value is None
    assert aggregate.grounding_score is None


def test_latency_percentiles_use_linear_interpolation() -> None:
    metric = latency_stats([40.0, 10.0, 20.0, 30.0])

    assert metric.sample_count == 4
    assert metric.p50_ms == 25.0
    assert metric.p95_ms == pytest.approx(38.5)
    assert metric.mean_ms == 25.0


def test_output_contract_rejects_noncontiguous_retrieval_ranks(
    cases: tuple[EvaluationCase, ...],
) -> None:
    payload = perfect_output(cases[0]).model_dump(mode="json")
    payload["retrieval"][0]["rank"] = 2

    with pytest.raises(ValidationError, match="contiguous"):
        SystemCaseOutput.model_validate(payload)


def test_output_contract_rejects_negative_latency(
    cases: tuple[EvaluationCase, ...],
) -> None:
    payload = deepcopy(perfect_output(cases[0]).model_dump(mode="json"))
    payload["stage_latency_ms"]["total"] = -1.0

    with pytest.raises(ValidationError, match="finite and non-negative"):
        SystemCaseOutput.model_validate(payload)


def test_output_contract_rejects_unpaired_retrieval_channel_observations(
    cases: tuple[EvaluationCase, ...],
) -> None:
    payload = perfect_output(cases[0]).model_dump(mode="json")
    payload["retrieval"][0]["vector_similarity"] = None

    with pytest.raises(ValidationError, match="observed together"):
        SystemCaseOutput.model_validate(payload)


def test_unexpected_extraction_is_included_as_false_positive(
    cases: tuple[EvaluationCase, ...],
) -> None:
    case = cases[0]
    output = perfect_output(case)
    output.extractions = [
        ExtractionObservation(
            extraction_type="risk",
            fields={"description": "invented risk"},
            span_ids=[case.expected_spans[0].marker_id],
        )
    ]

    metric = score_case(case, output).extraction

    assert metric.true_positive == 0
    assert metric.false_positive == 1
    assert metric.false_negative == 0
    assert metric.precision == 0.0


def test_duplicate_retrieval_markers_do_not_inflate_recall(
    cases: tuple[EvaluationCase, ...],
) -> None:
    case = cases[1]
    marker = case.expected_spans[0]
    output = perfect_output(case)
    output.retrieval = [
        RetrievalObservation(
            rank=1,
            chunk_id=hashlib.sha256(b"first").hexdigest(),
            source_id=marker.source_id,
            marker_ids=[marker.marker_id],
            rrf_score=1.0,
            vector_rank=1,
            vector_similarity=1.0,
        ),
        RetrievalObservation(
            rank=2,
            chunk_id=hashlib.sha256(b"second").hexdigest(),
            source_id=marker.source_id,
            marker_ids=[marker.marker_id],
            rrf_score=0.5,
            text_rank=1,
            text_score=0.5,
        ),
    ]

    metric = score_case(case, output).retrieval

    assert metric.hits_at_k["3"] == 1
    assert metric.recall_at_k["3"] == 0.5


def test_output_contract_rejects_replay_that_replaces_the_executed_task(
    cases: tuple[EvaluationCase, ...],
) -> None:
    payload = perfect_output(cases[24]).model_dump(mode="json")
    payload["approval_observations"][1]["task_ids"] = ["c1f33bb5-b77b-52e1-8f5a-657be69d10d4"]

    with pytest.raises(ValidationError, match="cumulative"):
        SystemCaseOutput.model_validate(payload)
