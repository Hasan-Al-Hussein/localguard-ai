"""Strict gold-data and system-under-test contracts for evaluation."""

from __future__ import annotations

import math
import re
import uuid
from collections.abc import Awaitable
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    """Reject contract drift instead of silently dropping evaluation evidence."""

    model_config = ConfigDict(extra="forbid", revalidate_instances="always")


class CaseCategory(StrEnum):
    GROUNDED = "grounded"
    INSUFFICIENT = "insufficient"
    INJECTION = "injection"
    ACTION = "action"


class TaskType(StrEnum):
    QUESTION_ANSWERING = "question_answering"
    STRUCTURED_EXTRACTION = "structured_extraction"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    PROMPT_INJECTION = "prompt_injection"
    ACTION_APPROVAL = "action_approval"


class ResultStatus(StrEnum):
    ANSWERED = "answered"
    UNANSWERABLE = "unanswerable"
    APPROVAL_REQUIRED = "approval_required"


class ActorRole(StrEnum):
    VIEWER = "viewer"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class ToolName(StrEnum):
    NONE = "NONE"
    SEARCH_DOCUMENTS = "search_documents"
    GET_DOCUMENT_SECTION = "get_document_section"
    PROPOSE_WORKFLOW_TASK = "propose_workflow_task"
    LIST_PENDING_APPROVALS = "list_pending_approvals"
    GET_AUDIT_EVENT = "get_audit_event"


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"
    EXPIRE = "expire"
    REPLAY = "replay"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"


class ForbiddenOutcome(StrEnum):
    UNSUPPORTED_CLAIM_ASSERTED = "unsupported_claim_asserted"
    INVALID_CITATION_ACCEPTED = "invalid_citation_accepted"
    DOCUMENT_INSTRUCTION_FOLLOWED = "document_instruction_followed"
    ROLE_ESCALATED = "role_escalated"
    SYSTEM_PROMPT_DISCLOSED = "system_prompt_disclosed"
    SENSITIVE_CONFIGURATION_DISCLOSED = "sensitive_configuration_disclosed"
    EXTERNAL_NETWORK_REQUEST = "external_network_request"
    AUDIT_SUPPRESSED = "audit_suppressed"
    FORGED_TOOL_CALL_EXECUTED = "forged_tool_call_executed"
    PROPOSAL_CREATED_WITHOUT_USER_ACTION = "proposal_created_without_user_action"
    WORKFLOW_TASK_CREATED_BEFORE_APPROVAL = "workflow_task_created_before_approval"
    PRIVILEGED_ACTION_EXECUTED_WITHOUT_APPROVAL = "privileged_action_executed_without_approval"
    PROPOSAL_PAYLOAD_MUTATED_AFTER_APPROVAL = "proposal_payload_mutated_after_approval"
    DUPLICATE_TASK_CREATED = "duplicate_task_created"


class Capability(StrEnum):
    RETRIEVAL = "retrieval"
    ANSWER = "answer"
    EXTRACTION = "extraction"
    TOOL_TRACE = "tool_trace"
    ACTION_PROPOSAL = "action_proposal"
    APPROVAL_RESUME = "approval_resume"
    POLICY_OBSERVABILITY = "policy_observability"
    STAGE_LATENCY = "stage_latency"


class ClaimOrigin(StrEnum):
    MODEL = "model"
    DETERMINISTIC_TEST_PROVIDER = "deterministic_test_provider"
    DETERMINISTIC_EVIDENCE_NORMALIZER = "deterministic_evidence_normalizer"


class FindingOrigin(StrEnum):
    MODEL = "model"
    DETERMINISTIC_TEST_PROVIDER = "deterministic_test_provider"
    DETERMINISTIC_EVIDENCE_NORMALIZER = "deterministic_evidence_normalizer"


class SpanReference(StrictModel):
    source_id: str = Field(pattern=r"^LG-(POL|ATK)-[0-9]{3}$")
    marker_id: str = Field(pattern=r"^LG-(POL|ATK)-[0-9]{3}:L[0-9]{3}$")

    @model_validator(mode="after")
    def marker_belongs_to_source(self) -> Self:
        if not self.marker_id.startswith(f"{self.source_id}:"):
            raise ValueError("span marker must belong to its source")
        return self


class GoldClaim(StrictModel):
    claim_id: str = Field(min_length=1, max_length=120)
    predicate: str = Field(min_length=1, max_length=160)
    normalized_value: str = Field(min_length=1, max_length=1000)
    span_ids: list[str] = Field(min_length=1)

    @field_validator("span_ids")
    @classmethod
    def unique_spans(cls, value: list[str]) -> list[str]:
        _require_marker_ids(value)
        if len(value) != len(set(value)):
            raise ValueError("claim span IDs must be unique")
        return value


class GoldExtraction(StrictModel):
    extraction_id: str = Field(min_length=1, max_length=120)
    extraction_type: Literal[
        "obligation", "deadline", "risk", "required_action", "responsible_party"
    ]
    fields: dict[str, str] = Field(min_length=1)
    span_ids: list[str] = Field(min_length=1)

    @field_validator("span_ids")
    @classmethod
    def validate_spans(cls, value: list[str]) -> list[str]:
        _require_marker_ids(value)
        if len(value) != len(set(value)):
            raise ValueError("extraction span IDs must be unique")
        return value


class GoldToolStep(StrictModel):
    step: int = Field(ge=1)
    tool_name: ToolName
    mode: Literal["read_only", "proposal_only"]
    reason: str = Field(min_length=1, max_length=1000)


class GoldProposal(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    priority: Literal["low", "medium", "high", "critical"]
    assignee_role: str = Field(min_length=1, max_length=160)
    due_at: str | None
    source_span_ids: list[str] = Field(min_length=1)
    approval_required: Literal[True]
    initial_status: Literal["pending"]
    expected_final_task_count: int = Field(ge=0, le=1)

    @field_validator("source_span_ids")
    @classmethod
    def validate_spans(cls, value: list[str]) -> list[str]:
        _require_marker_ids(value)
        if len(value) != len(set(value)):
            raise ValueError("proposal span IDs must be unique")
        return value


class GoldApprovalStep(StrictModel):
    step: int = Field(ge=1)
    decision: ApprovalDecision
    patch: dict[str, str]
    expected_proposal_status: ProposalStatus
    expected_task_count: int = Field(ge=0, le=1)


class EvaluationCase(StrictModel):
    case_id: str = Field(pattern=r"^LG-EVAL-(GRD|INS|INJ|ACT)-[0-9]{3}$")
    category: CaseCategory
    task_type: TaskType
    user_role: ActorRole
    request: str = Field(min_length=1, max_length=4000)
    corpus_scope: list[str] = Field(min_length=1)
    expected_status: ResultStatus
    expected_spans: list[SpanReference]
    expected_claims: list[GoldClaim]
    expected_extractions: list[GoldExtraction]
    expected_tool_trace: list[GoldToolStep]
    expected_proposal: GoldProposal | None
    approval_script: list[GoldApprovalStep]
    missing_facts: list[str]
    forbidden_outcomes: list[ForbiddenOutcome] = Field(min_length=1)


class ApprovalDecisionInput(StrictModel):
    """Only the human decision is supplied to the SUT; gold results stay hidden."""

    step: int = Field(ge=1)
    decision: ApprovalDecision
    patch: dict[str, str]


class EvaluationInput(StrictModel):
    dataset_version: str = Field(min_length=1, max_length=40)
    case_id: str = Field(pattern=r"^LG-EVAL-(GRD|INS|INJ|ACT)-[0-9]{3}$")
    task_type: TaskType
    request: str = Field(min_length=1, max_length=4000)
    actor_role: ActorRole
    corpus_scope: list[str] = Field(min_length=1)
    approval_decisions: list[ApprovalDecisionInput]

    @classmethod
    def from_case(cls, case: EvaluationCase, *, dataset_version: str) -> Self:
        return cls(
            dataset_version=dataset_version,
            case_id=case.case_id,
            task_type=case.task_type,
            request=case.request,
            actor_role=case.user_role,
            corpus_scope=case.corpus_scope,
            approval_decisions=[
                ApprovalDecisionInput(step=item.step, decision=item.decision, patch=item.patch)
                for item in case.approval_script
            ],
        )


class RetrievalObservation(StrictModel):
    rank: int = Field(ge=1, le=100)
    chunk_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_id: str = Field(pattern=r"^LG-(POL|ATK)-[0-9]{3}$")
    marker_ids: list[str]
    rrf_score: float = Field(ge=0)
    vector_rank: int | None = Field(default=None, ge=1)
    text_rank: int | None = Field(default=None, ge=1)
    vector_similarity: float | None = Field(default=None, ge=-1, le=1)
    text_score: float | None = Field(default=None, ge=0)

    @field_validator("marker_ids")
    @classmethod
    def unique_markers(cls, value: list[str]) -> list[str]:
        _require_marker_ids(value)
        if len(value) != len(set(value)):
            raise ValueError("retrieval marker IDs must be unique")
        return value

    @field_validator("rrf_score", "vector_similarity", "text_score")
    @classmethod
    def finite_score(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("retrieval score must be finite")
        return value

    @model_validator(mode="after")
    def has_observed_retrieval_channel(self) -> Self:
        if self.vector_rank is None and self.text_rank is None:
            raise ValueError("retrieval observation must include a vector or text rank")
        if (self.vector_rank is None) != (self.vector_similarity is None):
            raise ValueError("vector rank and similarity must be observed together")
        if (self.text_rank is None) != (self.text_score is None):
            raise ValueError("text rank and score must be observed together")
        return self

    @model_validator(mode="after")
    def markers_belong_to_source(self) -> Self:
        if any(not marker.startswith(f"{self.source_id}:") for marker in self.marker_ids):
            raise ValueError("retrieval markers must belong to the reported source")
        return self


class CitationObservation(StrictModel):
    source_id: str = Field(pattern=r"^LG-(POL|ATK)-[0-9]{3}$")
    marker_id: str = Field(pattern=r"^LG-(POL|ATK)-[0-9]{3}:L[0-9]{3}$")

    @model_validator(mode="after")
    def marker_belongs_to_source(self) -> Self:
        if not self.marker_id.startswith(f"{self.source_id}:"):
            raise ValueError("citation marker must belong to its source")
        return self


class ClaimObservation(StrictModel):
    predicate: str = Field(min_length=1, max_length=160)
    normalized_value: str = Field(min_length=1, max_length=1000)
    span_ids: list[str] = Field(min_length=1)

    @field_validator("span_ids")
    @classmethod
    def validate_spans(cls, value: list[str]) -> list[str]:
        _require_marker_ids(value)
        if len(value) != len(set(value)):
            raise ValueError("claim span IDs must be unique")
        return value


class ClaimProvenanceObservation(StrictModel):
    claim_index: int = Field(ge=0)
    predicate: str = Field(min_length=1, max_length=160)
    origin: ClaimOrigin
    normalizer_version: (
        Literal[
            "action-obligation-v1",
            "action-obligation-binding-v2",
            "qa-fact-binding-v1",
        ]
        | None
    ) = None
    source_marker_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    fallback_reason: (
        Literal[
            "duration_tuple_mismatch",
            "duration_unit_agreement",
            "evidence_binding_confirmed",
            "evidence_binding_selected",
            "performing_actor_scope",
            "predicate_not_grounded",
            "normalized_value_not_grounded",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def provenance_is_complete(self) -> Self:
        detail = (self.normalizer_version, self.source_marker_sha256, self.fallback_reason)
        if self.origin is ClaimOrigin.DETERMINISTIC_EVIDENCE_NORMALIZER:
            if any(value is None for value in detail):
                raise ValueError("normalizer claim provenance must be complete")
        elif any(value is not None for value in detail):
            raise ValueError("provider claim provenance cannot assert normalizer metadata")
        if self.normalizer_version == "qa-fact-binding-v1" and (
            self.fallback_reason != "evidence_binding_confirmed"
        ):
            raise ValueError("QA fact normalization requires confirmed-binding provenance")
        if self.fallback_reason == "evidence_binding_confirmed" and (
            self.normalizer_version != "qa-fact-binding-v1"
        ):
            raise ValueError("confirmed-binding claim provenance is reserved for QA facts")
        return self


class RuntimeModelIdentity(StrictModel):
    provider: Literal["deterministic", "ollama"]
    chat_model_name: str = Field(min_length=1, max_length=240)
    chat_model_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    embedding_model_name: str = Field(min_length=1, max_length=240)
    embedding_model_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    runtime_version: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def ollama_identity_is_digest_bound(self) -> Self:
        if self.provider == "ollama" and (
            self.chat_model_digest is None or self.embedding_model_digest is None
        ):
            raise ValueError("Ollama evaluation identity requires both resolved model digests")
        if self.provider == "deterministic" and (
            self.chat_model_digest is not None or self.embedding_model_digest is not None
        ):
            raise ValueError("deterministic test identity must not claim Ollama model digests")
        return self


class ProviderCallDiagnostic(StrictModel):
    """Bounded synthetic-evaluation evidence for one local chat attempt."""

    call_index: int = Field(ge=1, le=5)
    phase: Literal[
        "qa_initial",
        "qa_repair",
        "workflow_initial",
        "workflow_repair",
        "action_claim_repair",
        "binding_initial",
        "binding_repair",
    ]
    http_status: int | None = Field(default=None, ge=100, le=599)
    duration_ms: float = Field(ge=0)
    response_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    validation_stage: Literal[
        "transport",
        "protocol",
        "schema",
        "reference_binding",
        "semantic_grounding",
        "deterministic_normalization",
        "call_bound",
        "accepted",
    ]
    validation_hint: (
        Literal[
            "answer_must_match_grounded_schema",
            "complete_missing_grounded_action_claim",
            "invalid_or_incomplete_json",
            "insufficient_true_requires_empty_artifacts_and_null_proposal",
            "sufficient_action_requires_exactly_one_normalized_claim",
            "claim_predicate_must_be_semantic_lower_snake_case_not_a_marker_id",
            "claim_normalized_value_must_use_lower_snake_case",
            "claim_predicate_terms_must_match_the_cited_marker",
            "action_answer_claim_and_proposal_must_share_one_chunk_and_marker",
            "claim_duration_and_trigger_must_match_the_cited_marker",
            "action_output_requires_empty_findings",
            "sufficient_action_requires_non_null_proposal",
            "proposal_due_at_must_include_timezone_or_be_null",
            "marker_must_belong_to_its_cited_chunk",
            "chunk_id_must_come_from_allowed_evidence",
            "answer_must_contain_non_whitespace_text",
            "each_structured_finding_must_preserve_complete_actor_action_and_deadline_from_its_exact_marker",
            "structured_deadline_must_match_the_exact_bounded_marker_rule",
            "output_must_match_the_complete_workflow_schema",
            "select_every_and_only_directly_requested_binding",
            "select_exactly_one_directly_requested_action_binding",
            "sufficient_action_requires_one_claim_and_proposal_title_and_description_each_express_only_the_exact_cited_action_and_regulated_subject_with_bound_due",
            "duration_tuple_mismatch",
            "duration_unit_agreement",
            "performing_actor_scope",
            "predicate_not_grounded",
            "normalized_value_not_grounded",
        ]
        | None
    ) = None
    final_reason_code: (
        Literal[
            "generation_transport_failed",
            "generation_rejected",
            "generation_response_invalid",
            "model_schema_invalid",
            "evaluation_call_bound_exceeded",
        ]
        | None
    ) = None
    raw_excerpt: str | None = Field(default=None, max_length=4000)

    @field_validator("duration_ms")
    @classmethod
    def validate_duration(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("provider call duration must be finite")
        return value

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.raw_excerpt is not None and self.response_sha256 is None:
            raise ValueError("raw provider excerpts require a response digest")
        if self.validation_stage == "accepted" and self.final_reason_code is not None:
            raise ValueError("accepted provider calls cannot carry a terminal error code")
        if self.validation_stage == "call_bound":
            if (
                self.http_status is not None
                or self.response_sha256 is not None
                or self.raw_excerpt is not None
                or self.duration_ms != 0
                or self.final_reason_code != "evaluation_call_bound_exceeded"
            ):
                raise ValueError("call-bound denials cannot claim an executed provider response")
        elif self.final_reason_code == "evaluation_call_bound_exceeded":
            raise ValueError("call-bound terminal reasons require the call-bound stage")
        return self


class ExtractionObservation(StrictModel):
    extraction_type: Literal[
        "obligation", "deadline", "risk", "required_action", "responsible_party"
    ]
    fields: dict[str, str] = Field(min_length=1)
    span_ids: list[str] = Field(min_length=1)
    origin: FindingOrigin = FindingOrigin.MODEL
    normalizer_version: Literal["structured-obligation-binding-v2"] | None = None
    source_marker_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    derivation_reason: Literal["evidence_binding_confirmed"] | None = None

    @field_validator("span_ids")
    @classmethod
    def validate_spans(cls, value: list[str]) -> list[str]:
        _require_marker_ids(value)
        if len(value) != len(set(value)):
            raise ValueError("extraction span IDs must be unique")
        return value

    @model_validator(mode="after")
    def provenance_is_complete(self) -> Self:
        detail = (
            self.normalizer_version,
            self.source_marker_sha256,
            self.derivation_reason,
        )
        if self.origin is FindingOrigin.DETERMINISTIC_EVIDENCE_NORMALIZER:
            if any(value is None for value in detail):
                raise ValueError("normalizer finding provenance must be complete")
        elif any(value is not None for value in detail):
            raise ValueError("provider finding provenance cannot assert normalizer metadata")
        return self


class ProposalObservation(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    priority: Literal["low", "medium", "high", "critical"]
    assignee_role: str = Field(min_length=1, max_length=160)
    due_at: str | None
    source_span_ids: list[str] = Field(min_length=1)
    approval_required: bool
    initial_status: ProposalStatus
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("source_span_ids")
    @classmethod
    def validate_spans(cls, value: list[str]) -> list[str]:
        _require_marker_ids(value)
        if len(value) != len(set(value)):
            raise ValueError("proposal span IDs must be unique")
        return value


class ApprovalObservation(StrictModel):
    step: int = Field(ge=1)
    decision: ApprovalDecision
    proposal_status: ProposalStatus
    task_count: int = Field(ge=0)
    task_ids: list[uuid.UUID]
    payload_integrity_valid: bool

    @field_validator("task_ids")
    @classmethod
    def unique_task_ids(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(value) != len(set(value)):
            raise ValueError("task IDs must be unique")
        return value

    @model_validator(mode="after")
    def task_count_matches_identifiers(self) -> Self:
        if self.task_count != len(self.task_ids):
            raise ValueError("task count must match the observed task identifiers")
        return self


_ALLOWED_LATENCY_STAGES = frozenset(
    {"indexing", "embedding", "retrieval", "generation", "validation", "approval", "total"}
)


class SystemCaseOutput(StrictModel):
    """Observable behavior produced by the application, never by the gold scorer."""

    status: ResultStatus
    answer: str = Field(min_length=1, max_length=8000)
    retrieval: list[RetrievalObservation]
    citations: list[CitationObservation]
    claims: list[ClaimObservation]
    claim_provenance: list[ClaimProvenanceObservation]
    extractions: list[ExtractionObservation]
    tool_trace: list[ToolName]
    proposal: ProposalObservation | None
    approval_observations: list[ApprovalObservation]
    pre_approval_task_count: int = Field(ge=0)
    pre_approval_execution_count: int = Field(ge=0)
    observed_policy_failures: list[ForbiddenOutcome]
    stage_latency_ms: dict[str, float]
    trace_id: uuid.UUID

    @field_validator("stage_latency_ms")
    @classmethod
    def validate_latencies(cls, value: dict[str, float]) -> dict[str, float]:
        unknown = set(value) - _ALLOWED_LATENCY_STAGES
        if unknown:
            raise ValueError(f"unknown latency stages: {sorted(unknown)}")
        if "total" not in value:
            raise ValueError("total stage latency is required")
        if any(not math.isfinite(item) or item < 0 for item in value.values()):
            raise ValueError("stage latency must be finite and non-negative")
        return value

    @model_validator(mode="after")
    def validate_ordering(self) -> Self:
        ranks = [item.rank for item in self.retrieval]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("retrieval ranks must be contiguous and ordered from one")
        chunk_ids = [item.chunk_id for item in self.retrieval]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("retrieval chunk IDs must be unique")
        citations = [(item.source_id, item.marker_id) for item in self.citations]
        if len(citations) != len(set(citations)):
            raise ValueError("citations must be unique")
        if [item.claim_index for item in self.claim_provenance] != list(range(len(self.claims))):
            raise ValueError("claim provenance must be contiguous and cover every claim")
        if any(
            provenance.predicate != claim.predicate
            for claim, provenance in zip(self.claims, self.claim_provenance, strict=True)
        ):
            raise ValueError("claim provenance predicates must match semantic claims")
        steps = [item.step for item in self.approval_observations]
        if steps != list(range(1, len(steps) + 1)):
            raise ValueError("approval observations must be contiguous and ordered from one")
        prior_task_ids: set[uuid.UUID] = set()
        for observation in self.approval_observations:
            current_task_ids = set(observation.task_ids)
            if not prior_task_ids.issubset(current_task_ids):
                raise ValueError("approval task identifiers must be cumulative across decisions")
            prior_task_ids = current_task_ids
        if len(self.observed_policy_failures) != len(set(self.observed_policy_failures)):
            raise ValueError("observed policy failures must be unique")
        return self


class EvaluationSystem(Protocol):
    """Provider-injectable application boundary used by the evaluator."""

    @property
    def capabilities(self) -> frozenset[Capability]: ...

    @property
    def provider_raw_response_capture_enabled(self) -> bool: ...

    def run_case(self, request: EvaluationInput) -> Awaitable[SystemCaseOutput]: ...

    def runtime_identity(self) -> Awaitable[RuntimeModelIdentity]: ...

    def drain_provider_diagnostics(self) -> list[ProviderCallDiagnostic]: ...

    def aclose(self) -> Awaitable[None]: ...


class EvaluationSystemFactory(Protocol):
    def __call__(self, *, provider: str, repository_root: Path) -> EvaluationSystem: ...


_MARKER_PATTERN = re.compile(r"^LG-(?:POL|ATK)-[0-9]{3}:L[0-9]{3}$")


def _require_marker_ids(values: list[str]) -> None:
    if any(not _MARKER_PATTERN.fullmatch(value) for value in values):
        raise ValueError("span IDs must be stable corpus marker identifiers")
