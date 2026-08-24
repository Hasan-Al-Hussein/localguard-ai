"""Persist lossless structured-finding evidence and derivation provenance.

Revision ID: 20260823_0004
Revises: 20260823_0003
Create Date: 2026-08-23 21:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260823_0004"
down_revision: str | None = "20260823_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add exact marker, field, and derivation evidence without rewriting legacy meaning."""

    op.add_column(
        "extracted_findings",
        sa.Column(
            "cited_marker_ids",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "extracted_findings",
        sa.Column(
            "fields",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.add_column(
        "extracted_findings",
        sa.Column(
            "origin",
            sa.String(length=64),
            nullable=False,
            server_default="model",
        ),
    )
    op.add_column(
        "extracted_findings",
        sa.Column("normalizer_version", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "extracted_findings",
        sa.Column("source_marker_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "extracted_findings",
        sa.Column("derivation_reason", sa.String(length=80), nullable=True),
    )
    op.alter_column("extracted_findings", "cited_marker_ids", server_default=None)
    op.alter_column("extracted_findings", "fields", server_default=None)
    op.alter_column("extracted_findings", "origin", server_default=None)
    op.create_check_constraint(
        "ck_finding_origin",
        "extracted_findings",
        "origin IN ('model', 'deterministic_test_provider', 'deterministic_evidence_normalizer')",
    )
    op.create_check_constraint(
        "ck_finding_provenance_coherent",
        "extracted_findings",
        "(origin = 'deterministic_evidence_normalizer' "
        "AND normalizer_version IS NOT NULL "
        "AND source_marker_sha256 IS NOT NULL "
        "AND derivation_reason IS NOT NULL) "
        "OR (origin <> 'deterministic_evidence_normalizer' "
        "AND normalizer_version IS NULL "
        "AND source_marker_sha256 IS NULL "
        "AND derivation_reason IS NULL)",
    )
    op.create_check_constraint(
        "ck_finding_source_marker_sha256",
        "extracted_findings",
        "source_marker_sha256 IS NULL OR source_marker_sha256 ~ '^[0-9a-f]{64}$'",
    )
    op.create_check_constraint(
        "ck_finding_marker_ids_shape",
        "extracted_findings",
        "json_typeof(cited_marker_ids) = 'array' "
        "AND json_array_length(cited_marker_ids) <= 30",
    )
    op.create_check_constraint(
        "ck_finding_fields_shape",
        "extracted_findings",
        "json_typeof(fields) = 'object' "
        "AND jsonb_array_length("
        "jsonb_path_query_array(fields::jsonb, '$.keyvalue()')) <= 20",
    )
    op.create_check_constraint(
        "ck_finding_deterministic_payload",
        "extracted_findings",
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
    )


def downgrade() -> None:
    """Refuse to erase evidence-bearing finding metadata during downgrade."""

    bind = op.get_bind()
    evidence_rows = int(
        bind.execute(
            sa.text(
                "SELECT count(*) FROM extracted_findings "
                "WHERE origin <> 'model' "
                "OR normalizer_version IS NOT NULL "
                "OR source_marker_sha256 IS NOT NULL "
                "OR derivation_reason IS NOT NULL "
                "OR fields::text <> '{}' "
                "OR cited_marker_ids::text <> '[]'"
            )
        ).scalar_one()
    )
    if evidence_rows:
        raise RuntimeError(
            "cannot downgrade while extracted findings contain v2 evidence metadata; "
            "export and explicitly remove those findings first"
        )

    op.drop_constraint("ck_finding_deterministic_payload", "extracted_findings", type_="check")
    op.drop_constraint("ck_finding_fields_shape", "extracted_findings", type_="check")
    op.drop_constraint("ck_finding_marker_ids_shape", "extracted_findings", type_="check")
    op.drop_constraint("ck_finding_source_marker_sha256", "extracted_findings", type_="check")
    op.drop_constraint("ck_finding_provenance_coherent", "extracted_findings", type_="check")
    op.drop_constraint("ck_finding_origin", "extracted_findings", type_="check")
    op.drop_column("extracted_findings", "derivation_reason")
    op.drop_column("extracted_findings", "source_marker_sha256")
    op.drop_column("extracted_findings", "normalizer_version")
    op.drop_column("extracted_findings", "origin")
    op.drop_column("extracted_findings", "fields")
    op.drop_column("extracted_findings", "cited_marker_ids")
