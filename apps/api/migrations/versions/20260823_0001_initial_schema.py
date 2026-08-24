"""Create the Phase 1 document intelligence schema.

Revision ID: 20260823_0001
Revises: none
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR


revision: str = "20260823_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


role_enum = sa.Enum("viewer", "reviewer", "admin", name="role", native_enum=False)
document_state_enum = sa.Enum(
    "queued", "processing", "ready", "failed", "deleted", name="documentstate", native_enum=False
)
job_state_enum = sa.Enum("queued", "running", "succeeded", "failed", name="jobstate", native_enum=False)


def upgrade() -> None:
    """Create extensions, authoritative tables, constraints, and query indexes."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("role", role_enum, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)

    op.create_table(
        "login_throttles",
        sa.Column("principal_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("principal_hash"),
    )

    op.create_table(
        "sessions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("csrf_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent_hash", sa.LargeBinary(length=32), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_sessions_expires_at"), "sessions", ["expires_at"], unique=False)
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)

    op.create_table(
        "documents",
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column("current_revision_id", sa.UUID(), nullable=True),
        sa.Column("state", document_state_enum, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_documents_state"), "documents", ["state"], unique=False)

    op.create_table(
        "document_revisions",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=300), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("storage_key", sa.String(length=100), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("state", document_state_enum, nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_detail", sa.String(length=500), nullable=True),
        sa.Column("extracted_characters", sa.Integer(), nullable=True),
        sa.Column("anchor_count", sa.Integer(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "content_sha256", name="uq_document_revision_content"),
        sa.UniqueConstraint("document_id", "revision_number", name="uq_document_revision_number"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        op.f("ix_document_revisions_document_id"), "document_revisions", ["document_id"], unique=False
    )
    op.create_index(op.f("ix_document_revisions_state"), "document_revisions", ["state"], unique=False)
    op.create_foreign_key(
        "fk_document_current_revision",
        "documents",
        "document_revisions",
        ["current_revision_id"],
        ["id"],
    )

    op.create_table(
        "source_anchors",
        sa.Column("revision_id", sa.UUID(), nullable=False),
        sa.Column("stable_key", sa.String(length=220), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=300), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["revision_id"], ["document_revisions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("revision_id", "stable_key", name="uq_anchor_revision_key"),
    )
    op.create_index(op.f("ix_source_anchors_revision_id"), "source_anchors", ["revision_id"], unique=False)

    op.create_table(
        "chunks",
        sa.Column("revision_id", sa.UUID(), nullable=False),
        sa.Column("anchor_id", sa.UUID(), nullable=False),
        sa.Column("stable_id", sa.String(length=64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("embedding", VECTOR(dim=384), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["anchor_id"], ["source_anchors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revision_id"], ["document_revisions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("revision_id", "stable_id", name="uq_chunk_revision_stable_id"),
    )
    op.create_index(op.f("ix_chunks_anchor_id"), "chunks", ["anchor_id"], unique=False)
    op.create_index(op.f("ix_chunks_revision_id"), "chunks", ["revision_id"], unique=False)
    op.create_index("ix_chunks_revision_ordinal", "chunks", ["revision_id", "ordinal"], unique=False)
    op.create_index(op.f("ix_chunks_stable_id"), "chunks", ["stable_id"], unique=False)

    op.create_table(
        "question_jobs",
        sa.Column("requested_by_id", sa.UUID(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("document_ids", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("state", job_state_enum, nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_detail", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("requested_by_id", "idempotency_key", name="uq_question_idempotency"),
    )
    op.create_index(op.f("ix_question_jobs_state"), "question_jobs", ["state"], unique=False)

    op.create_table(
        "answers",
        sa.Column("question_job_id", sa.UUID(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("insufficient_evidence", sa.Boolean(), nullable=False),
        sa.Column("model_name", sa.String(length=160), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("retrieval_ms", sa.Float(), nullable=False),
        sa.Column("generation_ms", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["question_job_id"], ["question_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_job_id"),
    )

    op.create_table(
        "citations",
        sa.Column("answer_id", sa.UUID(), nullable=False),
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("revision_id", sa.UUID(), nullable=False),
        sa.Column("anchor_key", sa.String(length=220), nullable=False),
        sa.Column("anchor_label", sa.String(length=300), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["answer_id"], ["answers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["document_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("answer_id", "ordinal", name="uq_citation_answer_ordinal"),
    )
    op.create_index(op.f("ix_citations_answer_id"), "citations", ["answer_id"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=True),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_events_action"), "audit_events", ["action"], unique=False)
    op.create_index(op.f("ix_audit_events_actor_id"), "audit_events", ["actor_id"], unique=False)
    op.create_index(
        op.f("ix_audit_events_correlation_id"), "audit_events", ["correlation_id"], unique=False
    )
    op.create_index(op.f("ix_audit_events_occurred_at"), "audit_events", ["occurred_at"], unique=False)


def downgrade() -> None:
    """Remove the Phase 1 schema in dependency-safe order."""
    op.drop_index(op.f("ix_audit_events_occurred_at"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_correlation_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_actor_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_action"), table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index(op.f("ix_citations_answer_id"), table_name="citations")
    op.drop_table("citations")
    op.drop_table("answers")
    op.drop_index(op.f("ix_question_jobs_state"), table_name="question_jobs")
    op.drop_table("question_jobs")
    op.drop_index(op.f("ix_chunks_stable_id"), table_name="chunks")
    op.drop_index("ix_chunks_revision_ordinal", table_name="chunks")
    op.drop_index(op.f("ix_chunks_revision_id"), table_name="chunks")
    op.drop_index(op.f("ix_chunks_anchor_id"), table_name="chunks")
    op.drop_table("chunks")
    op.drop_index(op.f("ix_source_anchors_revision_id"), table_name="source_anchors")
    op.drop_table("source_anchors")
    op.drop_constraint("fk_document_current_revision", "documents", type_="foreignkey")
    op.drop_index(op.f("ix_document_revisions_state"), table_name="document_revisions")
    op.drop_index(op.f("ix_document_revisions_document_id"), table_name="document_revisions")
    op.drop_table("document_revisions")
    op.drop_index(op.f("ix_documents_state"), table_name="documents")
    op.drop_table("documents")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_expires_at"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("login_throttles")
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
