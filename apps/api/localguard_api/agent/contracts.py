"""Strict model-output and JSON-only graph-state contracts."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Literal, NotRequired, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..models import FindingType, TaskPriority


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


_MARKER_ID = re.compile(r"^LG-(?:POL|ATK)-[0-9]{3}:L[0-9]{3}$")
CLAIM_PREDICATE_PATTERN = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$"
CLAIM_VALUE_PATTERN = r"^[a-z0-9:]+(?:_[a-z0-9:]+)+$"
_CLAIM_PREDICATE = re.compile(CLAIM_PREDICATE_PATTERN)
_CLAIM_VALUE = re.compile(CLAIM_VALUE_PATTERN)


def _validate_marker_ids(values: list[str]) -> list[str]:
    if len(values) != len(set(values)):
        raise ValueError("source marker IDs must be unique")
    if any(_MARKER_ID.fullmatch(value) is None for value in values):
        raise ValueError("source marker IDs must use the stable corpus format")
    return values


class ClaimDraft(StrictModel):
    predicate: str = Field(min_length=1, max_length=160)
    normalized_value: str = Field(min_length=1, max_length=1000)
    cited_chunk_ids: list[str] = Field(min_length=1, max_length=10)
    cited_marker_ids: list[str] = Field(default_factory=list, max_length=30)
    origin: Literal["model", "deterministic_test_provider", "deterministic_evidence_normalizer"] = (
        "model"
    )
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

    @field_validator("predicate")
    @classmethod
    def semantic_predicate(cls, value: str) -> str:
        identifier_like = value.startswith(("lg_pol_", "lg_atk_")) or re.search(
            r"(?:^|_)l[0-9]{3}(?:_|$)", value
        )
        if _CLAIM_PREDICATE.fullmatch(value) is None or identifier_like:
            raise ValueError("claim predicate must use semantic lower_snake_case")
        return value

    @field_validator("normalized_value")
    @classmethod
    def normalized_machine_value(cls, value: str) -> str:
        if _CLAIM_VALUE.fullmatch(value) is None or not any(
            character.isalpha() for character in value
        ):
            raise ValueError("claim normalized value must use lower_snake_case")
        return value

    @field_validator("cited_chunk_ids")
    @classmethod
    def unique_citations(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("claim citations must be unique")
        return value

    _unique_markers = field_validator("cited_marker_ids")(_validate_marker_ids)

    @model_validator(mode="after")
    def validate_provenance(self) -> ClaimDraft:
        provenance = (
            self.normalizer_version,
            self.source_marker_sha256,
            self.fallback_reason,
        )
        if self.origin != "deterministic_evidence_normalizer" and any(
            value is not None for value in provenance
        ):
            raise ValueError("provider-authored claims cannot assert application provenance")
        if self.origin == "deterministic_evidence_normalizer" and any(
            value is None for value in provenance
        ):
            raise ValueError("deterministically normalized claims require complete provenance")
        if self.normalizer_version == "qa-fact-binding-v1" and (
            self.fallback_reason != "evidence_binding_confirmed"
        ):
            raise ValueError("QA fact normalization requires confirmed-binding provenance")
        if self.fallback_reason == "evidence_binding_confirmed" and (
            self.normalizer_version != "qa-fact-binding-v1"
        ):
            raise ValueError("confirmed-binding claim provenance is reserved for QA facts")
        return self


class FindingDraft(StrictModel):
    finding_type: FindingType
    summary: str = Field(min_length=1, max_length=1000)
    normalized_value: str | None = Field(default=None, max_length=500)
    responsible_party: str | None = Field(default=None, max_length=300)
    due_date: date | None = None
    severity: Literal["low", "medium", "high", "critical"] | None = None
    cited_chunk_ids: list[str] = Field(min_length=1, max_length=10)
    cited_marker_ids: list[str] = Field(default_factory=list, max_length=30)
    fields: dict[str, str] = Field(default_factory=dict, max_length=20)
    origin: Literal["model", "deterministic_test_provider", "deterministic_evidence_normalizer"] = (
        "model"
    )
    normalizer_version: Literal["structured-obligation-binding-v2"] | None = None
    source_marker_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    derivation_reason: Literal["evidence_binding_confirmed"] | None = None

    @field_validator("cited_chunk_ids")
    @classmethod
    def unique_citations(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("finding citations must be unique")
        return value

    _unique_markers = field_validator("cited_marker_ids")(_validate_marker_ids)

    @field_validator("fields")
    @classmethod
    def bounded_fields(cls, value: dict[str, str]) -> dict[str, str]:
        invalid = any(
            not key or len(key) > 80 or not item or len(item) > 1000 for key, item in value.items()
        )
        if invalid:
            raise ValueError("finding fields must contain bounded non-empty strings")
        return value

    @model_validator(mode="after")
    def validate_provenance(self) -> FindingDraft:
        provenance = (
            self.normalizer_version,
            self.source_marker_sha256,
            self.derivation_reason,
        )
        if self.origin != "deterministic_evidence_normalizer" and any(
            value is not None for value in provenance
        ):
            raise ValueError("provider-authored findings cannot assert application provenance")
        if self.origin == "deterministic_evidence_normalizer" and any(
            value is None for value in provenance
        ):
            raise ValueError("deterministically normalized findings require complete provenance")
        if self.origin == "deterministic_evidence_normalizer" and (
            set(self.fields) != {"actor", "action", "deadline"} or not self.cited_marker_ids
        ):
            raise ValueError(
                "deterministically normalized findings require exact fields and a source marker"
            )
        return self


class TaskProposalDraft(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=2000)
    assignee: str | None = Field(default=None, max_length=200)
    priority: TaskPriority = TaskPriority.MEDIUM
    due_at: datetime | None = None
    reasoning_summary: str = Field(min_length=1, max_length=1000)
    cited_chunk_ids: list[str] = Field(min_length=1, max_length=10)
    cited_marker_ids: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("cited_chunk_ids")
    @classmethod
    def unique_citations(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("proposal citations must be unique")
        return value

    _unique_markers = field_validator("cited_marker_ids")(_validate_marker_ids)

    @field_validator("due_at")
    @classmethod
    def require_aware_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("proposal due_at must include a timezone")
        return value.astimezone(UTC)


class WorkflowModelOutput(StrictModel):
    answer: str = Field(min_length=1, max_length=8000)
    cited_chunk_ids: list[str] = Field(default_factory=list, max_length=20)
    cited_marker_ids: list[str] = Field(default_factory=list, max_length=50)
    insufficient_evidence: bool
    claims: list[ClaimDraft] = Field(default_factory=list, max_length=50)
    findings: list[FindingDraft] = Field(default_factory=list, max_length=50)
    proposed_task: TaskProposalDraft | None = None

    @field_validator("cited_chunk_ids")
    @classmethod
    def unique_answer_citations(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("answer citations must be unique")
        return value

    _unique_markers = field_validator("cited_marker_ids")(_validate_marker_ids)

    @model_validator(mode="after")
    def validate_grounding_shape(self) -> WorkflowModelOutput:
        if self.insufficient_evidence and (
            self.cited_chunk_ids
            or self.cited_marker_ids
            or self.claims
            or self.findings
            or self.proposed_task is not None
        ):
            raise ValueError("insufficient output cannot contain grounded artifacts")
        if not self.insufficient_evidence and not self.cited_chunk_ids:
            raise ValueError("a grounded answer must cite at least one chunk")
        return self


def validate_action_output_shape(output: WorkflowModelOutput, *, action_requested: bool) -> None:
    """Require the bounded action artifact set at every provider and graph boundary."""

    proposal_required = action_requested and not output.insufficient_evidence
    if proposal_required != (output.proposed_task is not None):
        raise ValueError("workflow proposal does not match the application-classified request")
    if proposal_required and len(output.claims) != 1:
        raise ValueError("grounded action must contain exactly one normalized claim")
    if proposal_required and output.findings:
        raise ValueError("grounded action cannot contain extraction findings")


class RetrievalState(TypedDict):
    chunk_id: str
    database_chunk_id: str
    source_document_id: str
    revision_id: str
    document_title: str
    source_id: str | None
    marker_ids: list[str]
    anchor_key: str
    anchor_label: str
    start_offset: int
    end_offset: int
    content: str
    rrf_score: float
    vector_rank: int | None
    text_rank: int | None
    vector_similarity: float | None
    text_score: float | None


class WorkflowGraphState(TypedDict):
    thread_id: str
    actor_id: str
    actor_role: str
    question: str
    document_ids: list[str]
    origin_correlation_id: str
    intent: NotRequired[str]
    action_requested: NotRequired[bool]
    retrieval: NotRequired[list[RetrievalState]]
    sufficient: NotRequired[bool]
    answer: NotRequired[str]
    insufficient_evidence: NotRequired[bool]
    cited_chunk_ids: NotRequired[list[str]]
    cited_marker_ids: NotRequired[list[str]]
    claims: NotRequired[list[dict[str, object]]]
    findings: NotRequired[list[dict[str, object]]]
    proposal_draft: NotRequired[dict[str, object] | None]
    proposal_id: NotRequired[str]
    proposal_version: NotRequired[int]
    proposal_payload_hash: NotRequired[str]
    evidence_snapshot_hash: NotRequired[str]
    resume_decision: NotRequired[dict[str, object]]
    applied_decision_ids: NotRequired[list[str]]
    stage_latency_ms: NotRequired[dict[str, float]]
    tool_trace: NotRequired[list[str]]


class ApprovalResume(StrictModel):
    decision_id: str = Field(min_length=36, max_length=36)
    decision: Literal["approve", "reject", "edit"]
    proposal_id: str = Field(min_length=36, max_length=36)
    proposal_version: int = Field(ge=1)
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    replacement_proposal_id: str | None = Field(default=None, min_length=36, max_length=36)
    replacement_version: int | None = Field(default=None, ge=1)
    replacement_payload_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_replacement(self) -> ApprovalResume:
        replacement_values = (
            self.replacement_proposal_id,
            self.replacement_version,
            self.replacement_payload_hash,
        )
        if self.decision == "edit" and any(value is None for value in replacement_values):
            raise ValueError("edit resume requires a complete replacement proposal binding")
        if self.decision != "edit" and any(value is not None for value in replacement_values):
            raise ValueError("only edit resume may bind a replacement proposal")
        return self
