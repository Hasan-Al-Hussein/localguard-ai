"""Authoritative SQLAlchemy domain model for LocalGuard's persisted state."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, date, datetime
from typing import Any, ClassVar

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[object, object]] = {dict[str, Any]: JSON}


class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class Role(enum.StrEnum):
    VIEWER = "viewer"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class DocumentState(enum.StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class JobState(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class OutboxState(enum.StrEnum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    ACKNOWLEDGED = "acked"


class CleanupState(enum.StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"


class WorkflowState(enum.StrEnum):
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    REJECTED = "rejected"
    INSUFFICIENT = "insufficient"
    FAILED = "failed"


class FindingType(enum.StrEnum):
    OBLIGATION = "obligation"
    DEADLINE = "deadline"
    RESPONSIBLE_PARTY = "responsible_party"
    RISK = "risk"
    REQUIRED_ACTION = "required_action"


class ProposalState(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"
    EXECUTED = "executed"
    FAILED = "failed"


class DecisionKind(enum.StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


class TaskState(enum.StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def string_enum(enum_type: type[enum.Enum]) -> Enum:
    return Enum(enum_type, native_enum=False, values_callable=lambda e: [item.value for item in e])


class User(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[Role] = mapped_column(string_enum(Role), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SessionToken(UUIDPrimaryKey, Base):
    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True, nullable=False)
    csrf_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent_hash: Mapped[bytes | None] = mapped_column(LargeBinary(32))

    user: Mapped[User] = relationship(lazy="joined")


class LoginThrottle(Base):
    __tablename__ = "login_throttles"

    principal_hash: Mapped[bytes] = mapped_column(LargeBinary(32), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Document(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index(
            "uq_document_actor_content_active",
            "created_by_id",
            "source_content_sha256",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    source_content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    current_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_revisions.id", use_alter=True, name="fk_document_current_revision")
    )
    state: Mapped[DocumentState] = mapped_column(
        string_enum(DocumentState), default=DocumentState.QUEUED, nullable=False, index=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentRevision(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "document_revisions"
    __table_args__ = (
        UniqueConstraint("document_id", "revision_number", name="uq_document_revision_number"),
        UniqueConstraint("document_id", "content_sha256", name="uq_document_revision_content"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(300), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    state: Mapped[DocumentState] = mapped_column(
        string_enum(DocumentState), default=DocumentState.QUEUED, nullable=False, index=True
    )
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_detail: Mapped[str | None] = mapped_column(String(500))
    extracted_characters: Mapped[int | None] = mapped_column(Integer)
    anchor_count: Mapped[int | None] = mapped_column(Integer)
    origin_correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    document: Mapped[Document] = relationship(
        foreign_keys=[document_id], backref="revisions", lazy="joined"
    )


class SourceAnchor(UUIDPrimaryKey, Base):
    __tablename__ = "source_anchors"
    __table_args__ = (UniqueConstraint("revision_id", "stable_key", name="uq_anchor_revision_key"),)

    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_revisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stable_key: Mapped[str] = mapped_column(String(220), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)


class Chunk(UUIDPrimaryKey, Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("revision_id", "stable_id", name="uq_chunk_revision_stable_id"),
        Index("ix_chunks_revision_ordinal", "revision_id", "ordinal"),
    )

    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_revisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    anchor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_anchors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stable_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(VECTOR(384))

    anchor: Mapped[SourceAnchor] = relationship(lazy="joined")
    revision: Mapped[DocumentRevision] = relationship(lazy="joined")


class QuestionJob(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "question_jobs"
    __table_args__ = (
        UniqueConstraint("requested_by_id", "idempotency_key", name="uq_question_idempotency"),
    )

    requested_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    document_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    origin_correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state: Mapped[JobState] = mapped_column(
        string_enum(JobState), default=JobState.QUEUED, nullable=False, index=True
    )
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_detail: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Answer(UUIDPrimaryKey, Base):
    __tablename__ = "answers"

    question_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_jobs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    insufficient_evidence: Mapped[bool] = mapped_column(Boolean, nullable=False)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    retrieval_ms: Mapped[float] = mapped_column(Float, nullable=False)
    generation_ms: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Citation(UUIDPrimaryKey, Base):
    __tablename__ = "citations"
    __table_args__ = (UniqueConstraint("answer_id", "ordinal", name="uq_citation_answer_ordinal"),)

    answer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("answers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_revisions.id"), nullable=False
    )
    anchor_key: Mapped[str] = mapped_column(String(220), nullable=False)
    anchor_label: Mapped[str] = mapped_column(String(300), nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)


class AuditEvent(UUIDPrimaryKey, Base):
    __tablename__ = "audit_events"

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    causation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    thread_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(220), unique=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class OutboxEvent(UUIDPrimaryKey, Timestamped, Base):
    """Durable intent to dispatch a Celery task; Redis is never authoritative."""

    __tablename__ = "outbox_events"

    topic: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    origin_correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state: Mapped[OutboxState] = mapped_column(
        string_enum(OutboxState), default=OutboxState.PENDING, nullable=False, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    celery_task_id: Mapped[str | None] = mapped_column(String(80))
    last_error: Mapped[str | None] = mapped_column(String(300))


class CleanupEntry(UUIDPrimaryKey, Timestamped, Base):
    """Recoverable post-commit cleanup of private storage artifacts."""

    __tablename__ = "cleanup_entries"
    __table_args__ = (
        UniqueConstraint("resource_type", "resource_key", name="uq_cleanup_resource"),
    )

    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_key: Mapped[str] = mapped_column(String(220), nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    state: Mapped[CleanupState] = mapped_column(
        string_enum(CleanupState), default=CleanupState.PENDING, nullable=False, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(300))


class WorkflowRun(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint("requested_by_id", "idempotency_key", name="uq_workflow_run_idempotency"),
    )

    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    document_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    origin_correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state: Mapped[WorkflowState] = mapped_column(
        string_enum(WorkflowState), default=WorkflowState.RUNNING, nullable=False, index=True
    )
    intent: Mapped[str | None] = mapped_column(String(80))
    answer_text: Mapped[str | None] = mapped_column(Text)
    insufficient_evidence: Mapped[bool | None] = mapped_column(Boolean)
    cited_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_detail: Mapped[str | None] = mapped_column(String(500))


class ExtractedFinding(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "extracted_findings"
    __table_args__ = (
        UniqueConstraint("workflow_run_id", "stable_hash", name="uq_finding_run_hash"),
        CheckConstraint(
            "origin IN ('model', 'deterministic_test_provider', "
            "'deterministic_evidence_normalizer')",
            name="ck_finding_origin",
        ),
        CheckConstraint(
            "(origin = 'deterministic_evidence_normalizer' "
            "AND normalizer_version IS NOT NULL "
            "AND source_marker_sha256 IS NOT NULL "
            "AND derivation_reason IS NOT NULL) "
            "OR (origin <> 'deterministic_evidence_normalizer' "
            "AND normalizer_version IS NULL "
            "AND source_marker_sha256 IS NULL "
            "AND derivation_reason IS NULL)",
            name="ck_finding_provenance_coherent",
        ),
        CheckConstraint(
            "source_marker_sha256 IS NULL OR source_marker_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_finding_source_marker_sha256",
        ),
        CheckConstraint(
            "json_typeof(cited_marker_ids) = 'array' AND json_array_length(cited_marker_ids) <= 30",
            name="ck_finding_marker_ids_shape",
        ),
        CheckConstraint(
            "json_typeof(fields) = 'object' AND jsonb_array_length("
            "jsonb_path_query_array(fields::jsonb, '$.keyvalue()')) <= 20",
            name="ck_finding_fields_shape",
        ),
        CheckConstraint(
            "origin <> 'deterministic_evidence_normalizer' OR ("
            "normalizer_version = 'structured-obligation-binding-v2' "
            "AND derivation_reason = 'evidence_binding_confirmed' "
            "AND json_array_length(cited_marker_ids) >= 1 "
            "AND jsonb_array_length("
            "jsonb_path_query_array(fields::jsonb, '$.keyvalue()')) = 3 "
            "AND fields::jsonb ?& ARRAY['actor', 'action', 'deadline'] "
            "AND jsonb_typeof(fields::jsonb -> 'actor') = 'string' "
            "AND jsonb_typeof(fields::jsonb -> 'action') = 'string' "
            "AND jsonb_typeof(fields::jsonb -> 'deadline') = 'string' "
            "AND length(fields ->> 'actor') > 0 "
            "AND length(fields ->> 'action') > 0 "
            "AND length(fields ->> 'deadline') > 0)",
            name="ck_finding_deterministic_payload",
        ),
    )

    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_type: Mapped[FindingType] = mapped_column(
        string_enum(FindingType), nullable=False, index=True
    )
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(String(500))
    responsible_party: Mapped[str | None] = mapped_column(String(300))
    due_date: Mapped[date | None] = mapped_column(Date)
    severity: Mapped[str | None] = mapped_column(String(40))
    cited_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    cited_marker_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    fields: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    origin: Mapped[str] = mapped_column(String(64), default="model", nullable=False)
    normalizer_version: Mapped[str | None] = mapped_column(String(80))
    source_marker_sha256: Mapped[str | None] = mapped_column(String(64))
    derivation_reason: Mapped[str | None] = mapped_column(String(80))
    stable_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class ActionProposal(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "action_proposals"
    __table_args__ = (
        UniqueConstraint("workflow_run_id", "version", name="uq_proposal_run_version"),
        UniqueConstraint("workflow_run_id", "payload_hash", name="uq_proposal_run_payload_hash"),
    )

    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    previous_proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("action_proposals.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(80), nullable=False, default="create_workflow_task")
    state: Mapped[ProposalState] = mapped_column(
        string_enum(ProposalState), default=ProposalState.PENDING, nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    assignee: Mapped[str | None] = mapped_column(String(200))
    priority: Mapped[TaskPriority] = mapped_column(
        string_enum(TaskPriority), default=TaskPriority.MEDIUM, nullable=False
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reasoning_summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    cited_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    canonical_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class ApprovalDecision(UUIDPrimaryKey, Base):
    __tablename__ = "approval_decisions"
    __table_args__ = (UniqueConstraint("proposal_id", name="uq_decision_proposal"),)

    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("action_proposals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    proposal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    decided_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    decision: Mapped[DecisionKind] = mapped_column(string_enum(DecisionKind), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(1000))
    replacement_proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("action_proposals.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkflowTask(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "workflow_tasks"

    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("action_proposals.id"), unique=True, nullable=False, index=True
    )
    approval_decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("approval_decisions.id"), unique=True, nullable=False
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    assignee: Mapped[str | None] = mapped_column(String(200))
    priority: Mapped[TaskPriority] = mapped_column(string_enum(TaskPriority), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[TaskState] = mapped_column(
        string_enum(TaskState), default=TaskState.OPEN, nullable=False, index=True
    )


class MCPAccessToken(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "mcp_access_tokens"

    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(lazy="joined")
