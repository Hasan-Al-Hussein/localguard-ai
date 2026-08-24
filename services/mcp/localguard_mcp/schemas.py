"""Bounded MCP tool contracts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Generic, TypeVar

from localguard_api.models import ProposalState, Role, TaskPriority
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrustedPrincipal(StrictModel):
    user_id: uuid.UUID
    username: str
    role: Role


class ToolErrorBody(StrictModel):
    code: str
    message: str


T = TypeVar("T")


class ToolEnvelope(StrictModel, Generic[T]):  # noqa: UP046 - Python 3.11 compatibility
    ok: bool
    data: T | None = None
    error: ToolErrorBody | None = None

    @model_validator(mode="after")
    def validate_envelope(self) -> ToolEnvelope[T]:
        if self.ok != (self.error is None):
            raise ValueError("successful responses cannot contain errors")
        if self.ok and self.data is None:
            raise ValueError("successful responses require data")
        return self


class SearchDocumentsInput(StrictModel):
    query: str = Field(min_length=3, max_length=4000)
    document_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    limit: int = Field(default=8, ge=1, le=20)


class SearchHit(StrictModel):
    chunk_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_id: uuid.UUID
    document_title: str
    anchor_key: str
    anchor_label: str
    excerpt: str
    score: float
    vector_similarity: float | None
    text_score: float | None


class SearchDocumentsOutput(StrictModel):
    sufficient: bool
    hits: list[SearchHit]


class GetDocumentSectionInput(StrictModel):
    document_id: uuid.UUID
    anchor_key: str = Field(min_length=1, max_length=220, pattern=r"^[A-Za-z0-9:_-]+$")
    offset: int = Field(default=0, ge=0, le=500_000)
    max_chars: int = Field(default=4000, ge=1, le=8000)


class DocumentSectionOutput(StrictModel):
    document_id: uuid.UUID
    revision_id: uuid.UUID
    anchor_key: str
    anchor_label: str
    kind: str
    start_offset: int = Field(ge=0, le=500_000)
    end_offset: int = Field(ge=1, le=500_000)
    total_characters: int = Field(ge=1, le=500_000)
    truncated: bool
    text: str = Field(min_length=1, max_length=8000)

    @model_validator(mode="after")
    def validate_range(self) -> DocumentSectionOutput:
        if not self.start_offset < self.end_offset <= self.total_characters:
            raise ValueError("section output offsets are inconsistent")
        if len(self.text) != self.end_offset - self.start_offset:
            raise ValueError("section text length must match its offsets")
        if self.truncated != (self.end_offset < self.total_characters):
            raise ValueError("section truncation flag must match its offsets")
        return self


class ProposeWorkflowTaskInput(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=2000)
    assignee: str | None = Field(default=None, max_length=200)
    priority: TaskPriority = TaskPriority.MEDIUM
    due_at: datetime | None = None
    reasoning_summary: str = Field(min_length=1, max_length=1000)
    cited_chunk_ids: list[str] = Field(min_length=1, max_length=10)

    @field_validator("due_at")
    @classmethod
    def require_aware_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("due_at must include a timezone")
        return value.astimezone(UTC)

    @field_validator("cited_chunk_ids")
    @classmethod
    def validate_citations(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("citation IDs must be unique")
        if any(
            len(item) != 64 or any(character not in "0123456789abcdef" for character in item)
            for item in value
        ):
            raise ValueError("citation IDs must be lowercase SHA-256 identifiers")
        return value


class ProposalOutput(StrictModel):
    proposal_id: uuid.UUID
    thread_id: uuid.UUID
    version: int
    status: ProposalState
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_required: bool


class ListPendingApprovalsInput(StrictModel):
    limit: int = Field(default=25, ge=1, le=100)


class PendingApproval(StrictModel):
    proposal_id: uuid.UUID
    thread_id: uuid.UUID
    version: int
    title: str
    priority: TaskPriority
    due_at: datetime | None
    expires_at: datetime
    payload_hash: str


class PendingApprovalsOutput(StrictModel):
    items: list[PendingApproval]


class GetAuditEventInput(StrictModel):
    event_id: uuid.UUID


class AuditEventOutput(StrictModel):
    event_id: uuid.UUID
    occurred_at: datetime
    actor_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: uuid.UUID | None
    outcome: str
    correlation_id: str
    causation_id: str | None
    thread_id: uuid.UUID | None
    detail: dict[str, object]
