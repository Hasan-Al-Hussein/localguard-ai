"""Explicit public request and response contracts."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import DocumentState, JobState, Role


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserPublic(ORMModel):
    id: uuid.UUID
    username: str
    display_name: str
    role: Role


class LoginRequest(StrictModel):
    username: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class LoginResponse(StrictModel):
    user: UserPublic
    csrf_token: str


class CSRFResponse(StrictModel):
    csrf_token: str


class MessageResponse(StrictModel):
    message: str


class AnchorPublic(ORMModel):
    id: uuid.UUID
    stable_key: str
    kind: str
    label: str
    ordinal: int
    start_offset: int
    end_offset: int
    text: str


class RevisionSectionPublic(StrictModel):
    document_id: uuid.UUID
    revision_id: uuid.UUID
    anchor_key: str
    anchor_label: str
    kind: str
    anchor_start_offset: int
    anchor_end_offset: int
    requested_start_offset: int
    requested_end_offset: int
    text: str


class RevisionPublic(ORMModel):
    id: uuid.UUID
    revision_number: int
    original_filename: str
    media_type: str
    byte_size: int
    content_sha256: str
    state: DocumentState
    extracted_characters: int | None
    anchor_count: int | None
    created_at: datetime


class DocumentSummary(ORMModel):
    id: uuid.UUID
    title: str
    state: DocumentState
    current_revision_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class DocumentDetail(DocumentSummary):
    current_revision: RevisionPublic | None = None
    anchors: list[AnchorPublic] = Field(default_factory=list)


class DocumentList(StrictModel):
    items: list[DocumentSummary]
    total: int
    offset: int
    limit: int


class UploadAccepted(StrictModel):
    document: DocumentSummary
    revision_id: uuid.UUID
    ingestion_job_id: str | None = None
    duplicate: bool = False


class QuestionRequest(StrictModel):
    question: str = Field(min_length=3, max_length=4000)
    document_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 3:
            raise ValueError("question is empty after normalization")
        return normalized


class CitationPublic(ORMModel):
    id: uuid.UUID
    ordinal: int
    quote: str
    document_id: uuid.UUID
    revision_id: uuid.UUID
    anchor_key: str
    anchor_label: str
    start_offset: int
    end_offset: int


class AnswerPublic(ORMModel):
    id: uuid.UUID
    text: str
    insufficient_evidence: bool
    model_name: str
    prompt_version: str
    retrieval_ms: float
    generation_ms: float
    created_at: datetime
    citations: list[CitationPublic] = Field(default_factory=list)


class QuestionJobPublic(ORMModel):
    id: uuid.UUID
    question: str
    document_ids: list[str]
    state: JobState
    error_code: str | None
    error_detail: str | None
    created_at: datetime
    updated_at: datetime
    answer: AnswerPublic | None = None


class DeadlineSummary(ORMModel):
    id: uuid.UUID
    workflow_run_id: uuid.UUID
    summary: str
    due_date: date
    severity: str | None


class ActivitySummary(ORMModel):
    id: uuid.UUID
    occurred_at: datetime
    action: str
    resource_type: str
    resource_id: uuid.UUID | None
    outcome: str
    correlation_id: str


class EvaluationOverview(StrictModel):
    run_id: str
    schema_version: str | None
    runtime_provider: str | None
    completed_case_count: int | None
    case_count: int | None
    safety_passed: bool | None
    quality_passed: bool | None
    run_passed: bool | None
    integrity_status: Literal[
        "summary_verified", "run_verified", "corrupt", "unsupported_schema", "hash_mismatch"
    ]
    integrity_note: str
    comparability_status: Literal["current", "legacy_metadata_only", "unavailable"]
    comparability_note: str


class OverviewPublic(StrictModel):
    documents_total: int
    documents_ready: int
    documents_processing: int
    questions_total: int
    questions_failed: int
    recent_documents: list[DocumentSummary]
    pending_approvals: int
    extracted_deadlines: list[DeadlineSummary]
    recent_activity: list[ActivitySummary]
    evaluation_summary: EvaluationOverview | None = None


class HealthResponse(StrictModel):
    status: str
    checks: dict[str, str] = Field(default_factory=dict)


class ErrorBody(StrictModel):
    code: str
    message: str
    correlation_id: str


class ErrorResponse(StrictModel):
    error: ErrorBody
