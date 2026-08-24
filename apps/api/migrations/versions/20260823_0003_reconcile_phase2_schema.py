"""Reconcile databases upgraded by the pre-final Phase 2 revision.

Revision ID: 20260823_0003
Revises: c57f8be7e15c
Create Date: 2026-08-23 10:25:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260823_0003"
down_revision: str | None = "c57f8be7e15c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _unique_constraints(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {
        str(constraint["name"])
        for constraint in inspector.get_unique_constraints(table_name)
        if constraint.get("name") is not None
    }


def _indexes(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {
        str(index["name"])
        for index in inspector.get_indexes(table_name)
        if index.get("name") is not None
    }


def upgrade() -> None:
    """Normalize both fresh and historically upgraded c57 databases."""

    if not _has_column("workflow_runs", "idempotency_key"):
        op.add_column(
            "workflow_runs",
            sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        )
        op.execute(
            "UPDATE workflow_runs "
            "SET idempotency_key = 'legacy-' || replace(id::text, '-', '') "
            "WHERE idempotency_key IS NULL"
        )
        op.alter_column("workflow_runs", "idempotency_key", nullable=False)

    if "uq_workflow_run_idempotency" not in _unique_constraints("workflow_runs"):
        op.create_unique_constraint(
            "uq_workflow_run_idempotency",
            "workflow_runs",
            ["requested_by_id", "idempotency_key"],
        )

    document_constraints = _unique_constraints("documents")
    if "uq_document_actor_content" in document_constraints:
        op.drop_constraint("uq_document_actor_content", "documents", type_="unique")
    elif "uq_document_actor_content" in _indexes("documents"):
        op.drop_index("uq_document_actor_content", table_name="documents")

    if "uq_document_actor_content_active" not in _indexes("documents"):
        op.create_index(
            "uq_document_actor_content_active",
            "documents",
            ["created_by_id", "source_content_sha256"],
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
        )

    # SQLAlchemy's non-native Enum did not consistently create a check across
    # dependency versions. Remove only a historical state check that excludes
    # the finalized durable acknowledgement value.
    op.execute(
        """
        DO $$
        DECLARE
            legacy_check RECORD;
        BEGIN
            FOR legacy_check IN
                SELECT constraint_row.conname
                FROM pg_constraint AS constraint_row
                JOIN pg_class AS table_row
                  ON table_row.oid = constraint_row.conrelid
                WHERE table_row.relname = 'outbox_events'
                  AND constraint_row.contype = 'c'
                  AND pg_get_constraintdef(constraint_row.oid) ILIKE '%state%'
                  AND pg_get_constraintdef(constraint_row.oid) NOT ILIKE '%acked%'
            LOOP
                EXECUTE format(
                    'ALTER TABLE outbox_events DROP CONSTRAINT %I',
                    legacy_check.conname
                );
            END LOOP;
        END
        $$
        """
    )


def downgrade() -> None:
    """Keep the finalized c57 shape; this revision only repairs historical drift."""
