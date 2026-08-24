"""Typed factories for evaluation metric and runner tests."""

from __future__ import annotations

import hashlib
import uuid

from localguard_api.evaluation.contracts import (
    ApprovalObservation,
    CitationObservation,
    ClaimObservation,
    ClaimOrigin,
    ClaimProvenanceObservation,
    EvaluationCase,
    ExtractionObservation,
    FindingOrigin,
    ProposalObservation,
    RetrievalObservation,
    SystemCaseOutput,
)


def perfect_output(case: EvaluationCase) -> SystemCaseOutput:
    retrieval = [
        RetrievalObservation(
            rank=index,
            chunk_id=hashlib.sha256(f"{case.case_id}:chunk:{index}".encode()).hexdigest(),
            source_id=span.source_id,
            marker_ids=[span.marker_id],
            rrf_score=1.0 / index,
            vector_rank=index,
            text_rank=index,
            vector_similarity=1.0 / index,
            text_score=1.0 / index,
        )
        for index, span in enumerate(case.expected_spans, start=1)
    ]
    citations = [
        CitationObservation(source_id=item.source_id, marker_id=item.marker_id)
        for item in case.expected_spans
    ]
    proposal = None
    if case.expected_proposal is not None:
        expected = case.expected_proposal
        proposal = ProposalObservation(
            title=expected.title,
            description=expected.description,
            priority=expected.priority,
            assignee_role=expected.assignee_role,
            due_at=expected.due_at,
            source_span_ids=expected.source_span_ids,
            approval_required=expected.approval_required,
            initial_status=expected.initial_status,
            payload_hash="0" * 64,
        )
    claims = [
        ClaimObservation(
            predicate=item.predicate,
            normalized_value=item.normalized_value,
            span_ids=item.span_ids,
        )
        for item in case.expected_claims
    ]
    return SystemCaseOutput(
        status=case.expected_status,
        answer=(
            "The available evidence is insufficient to answer this question."
            if case.expected_status.value == "unanswerable"
            else "Synthetic, grounded test answer."
        ),
        retrieval=retrieval,
        citations=citations,
        claims=claims,
        claim_provenance=[
            ClaimProvenanceObservation(
                claim_index=index,
                predicate=claim.predicate,
                origin=ClaimOrigin.DETERMINISTIC_TEST_PROVIDER,
            )
            for index, claim in enumerate(claims)
        ],
        extractions=[
            ExtractionObservation(
                extraction_type=item.extraction_type,
                fields=item.fields,
                span_ids=item.span_ids,
                origin=FindingOrigin.DETERMINISTIC_TEST_PROVIDER,
            )
            for item in case.expected_extractions
        ],
        tool_trace=[item.tool_name for item in case.expected_tool_trace],
        proposal=proposal,
        approval_observations=[
            ApprovalObservation(
                step=item.step,
                decision=item.decision,
                proposal_status=item.expected_proposal_status,
                task_count=item.expected_task_count,
                task_ids=[uuid.uuid5(uuid.NAMESPACE_URL, f"{case.case_id}:task:1")]
                if item.expected_task_count
                else [],
                payload_integrity_valid=True,
            )
            for item in case.approval_script
        ],
        pre_approval_task_count=0,
        pre_approval_execution_count=0,
        observed_policy_failures=[],
        stage_latency_ms={
            "retrieval": 2.0,
            "generation": 3.0,
            "validation": 1.0,
            "total": 6.0,
        },
        trace_id=uuid.uuid5(uuid.NAMESPACE_URL, f"{case.case_id}:trace"),
    )
