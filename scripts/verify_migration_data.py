"""Data-bearing PostgreSQL probes for the LocalGuard migration chain."""

from __future__ import annotations

import argparse
import asyncio
import os
from collections.abc import Awaitable, Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

INITIAL_REVISION = "20260823_0001"
PHASE2_REVISION = "c57f8be7e15c"
PHASE3_REVISION = "20260823_0003"
HEAD_REVISION = "20260823_0004"

LEGACY_USER_ID = "00000000-0000-0000-0000-00000000a001"
CANONICAL_DOCUMENT_ID = "00000000-0000-0000-0000-00000000d001"
DUPLICATE_DOCUMENT_ID = "00000000-0000-0000-0000-00000000d002"
CANONICAL_REVISION_ID = "00000000-0000-0000-0000-00000000e001"
DUPLICATE_REVISION_ID = "00000000-0000-0000-0000-00000000e002"
HISTORICAL_USER_ID = "00000000-0000-0000-0000-00000000a101"
HISTORICAL_WORKFLOW_ID = "00000000-0000-0000-0000-00000000f101"
ORPHAN_QUESTION_ID = "00000000-0000-0000-0000-00000000f201"
ORPHAN_ANSWER_ID = "00000000-0000-0000-0000-00000000f202"
ORPHAN_CITATION_ID = "00000000-0000-0000-0000-00000000f203"
FINDING_WORKFLOW_ID = "00000000-0000-0000-0000-00000000f301"
LEGACY_FINDING_ID = "00000000-0000-0000-0000-00000000f302"
DERIVED_FINDING_ID = "00000000-0000-0000-0000-00000000f303"
SHARED_CONTENT_SHA = "a" * 64


async def _revision(connection: AsyncConnection) -> str:
    value = await connection.scalar(text("SELECT version_num FROM alembic_version"))
    if not isinstance(value, str):
        raise RuntimeError("Alembic revision is unavailable")
    return value


async def _require_revision(connection: AsyncConnection, expected: str) -> None:
    actual = await _revision(connection)
    if actual != expected:
        raise RuntimeError(f"Expected Alembic revision {expected}, received {actual}")


async def seed_legacy_duplicates(connection: AsyncConnection) -> None:
    await _require_revision(connection, INITIAL_REVISION)
    existing = await connection.scalar(
        text("SELECT count(*) FROM users WHERE id = CAST(:user_id AS uuid)"),
        {"user_id": LEGACY_USER_ID},
    )
    if existing != 0:
        raise RuntimeError("Migration duplicate probe already exists")

    await connection.execute(
        text(
            "INSERT INTO users "
            "(username, display_name, password_hash, role, is_active, id, created_at, updated_at) "
            "VALUES ('migration-duplicate-user', 'Migration Duplicate User', "
            "'not-a-login-password-hash', 'admin', true, CAST(:user_id AS uuid), "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {"user_id": LEGACY_USER_ID},
    )
    await connection.execute(
        text(
            "INSERT INTO documents "
            "(title, created_by_id, current_revision_id, state, deleted_at, id, "
            "created_at, updated_at) "
            "VALUES "
            "('Canonical legacy document', CAST(:user_id AS uuid), NULL, 'ready', NULL, "
            " CAST(:canonical_id AS uuid), CURRENT_TIMESTAMP - INTERVAL '2 minutes', "
            " CURRENT_TIMESTAMP - INTERVAL '2 minutes'), "
            "('Duplicate legacy document', CAST(:user_id AS uuid), NULL, 'ready', NULL, "
            " CAST(:duplicate_id AS uuid), CURRENT_TIMESTAMP - INTERVAL '1 minute', "
            " CURRENT_TIMESTAMP - INTERVAL '1 minute')"
        ),
        {
            "user_id": LEGACY_USER_ID,
            "canonical_id": CANONICAL_DOCUMENT_ID,
            "duplicate_id": DUPLICATE_DOCUMENT_ID,
        },
    )
    await connection.execute(
        text(
            "INSERT INTO document_revisions "
            "(document_id, revision_number, original_filename, media_type, storage_key, "
            " content_sha256, byte_size, state, error_code, error_detail, extracted_characters, "
            " anchor_count, id, created_at, updated_at) "
            "VALUES "
            "(CAST(:canonical_id AS uuid), 1, 'canonical.txt', 'text/plain', "
            " 'migration-probe-canonical.txt', :digest, 10, 'ready', NULL, NULL, 10, 0, "
            " CAST(:canonical_revision_id AS uuid), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP), "
            "(CAST(:duplicate_id AS uuid), 1, 'duplicate.txt', 'text/plain', "
            " 'migration-probe-duplicate.txt', :digest, 10, 'ready', NULL, NULL, 10, 0, "
            " CAST(:duplicate_revision_id AS uuid), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {
            "canonical_id": CANONICAL_DOCUMENT_ID,
            "duplicate_id": DUPLICATE_DOCUMENT_ID,
            "canonical_revision_id": CANONICAL_REVISION_ID,
            "duplicate_revision_id": DUPLICATE_REVISION_ID,
            "digest": SHARED_CONTENT_SHA,
        },
    )
    await connection.execute(
        text(
            "UPDATE documents SET current_revision_id = CASE "
            "WHEN id = CAST(:canonical_id AS uuid) THEN CAST(:canonical_revision_id AS uuid) "
            "ELSE CAST(:duplicate_revision_id AS uuid) END "
            "WHERE id IN (CAST(:canonical_id AS uuid), CAST(:duplicate_id AS uuid))"
        ),
        {
            "canonical_id": CANONICAL_DOCUMENT_ID,
            "duplicate_id": DUPLICATE_DOCUMENT_ID,
            "canonical_revision_id": CANONICAL_REVISION_ID,
            "duplicate_revision_id": DUPLICATE_REVISION_ID,
        },
    )


async def assert_quarantined(connection: AsyncConnection) -> None:
    await _require_revision(connection, HEAD_REVISION)
    rows = (
        await connection.execute(
            text(
                "SELECT id::text, state, deleted_at IS NOT NULL, source_content_sha256 "
                "FROM documents "
                "WHERE id IN (CAST(:canonical_id AS uuid), CAST(:duplicate_id AS uuid)) "
                "ORDER BY id"
            ),
            {
                "canonical_id": CANONICAL_DOCUMENT_ID,
                "duplicate_id": DUPLICATE_DOCUMENT_ID,
            },
        )
    ).all()
    expected = [
        (CANONICAL_DOCUMENT_ID, "ready", False, SHARED_CONTENT_SHA),
        (DUPLICATE_DOCUMENT_ID, "deleted", True, SHARED_CONTENT_SHA),
    ]
    if [tuple(row) for row in rows] != expected:
        raise RuntimeError(f"Unexpected duplicate quarantine rows: {rows!r}")

    revision_count = await connection.scalar(
        text(
            "SELECT count(*) FROM document_revisions "
            "WHERE document_id IN (CAST(:canonical_id AS uuid), CAST(:duplicate_id AS uuid))"
        ),
        {
            "canonical_id": CANONICAL_DOCUMENT_ID,
            "duplicate_id": DUPLICATE_DOCUMENT_ID,
        },
    )
    if revision_count != 2:
        raise RuntimeError("Quarantine did not preserve both legacy revisions")

    audit = (
        await connection.execute(
            text(
                "SELECT outcome, detail ->> 'canonical_document_id', "
                "detail ->> 'previous_state' "
                "FROM audit_events "
                "WHERE action = 'migration.document_duplicate_quarantined' "
                "AND resource_id = CAST(:duplicate_id AS uuid)"
            ),
            {"duplicate_id": DUPLICATE_DOCUMENT_ID},
        )
    ).one_or_none()
    if audit is None or tuple(audit) != (
        "quarantined",
        CANONICAL_DOCUMENT_ID,
        "ready",
    ):
        raise RuntimeError(f"Missing duplicate quarantine audit: {audit!r}")


async def assert_restored(connection: AsyncConnection) -> None:
    await _require_revision(connection, INITIAL_REVISION)
    rows = (
        await connection.execute(
            text(
                "SELECT id::text, state, deleted_at IS NULL FROM documents "
                "WHERE id IN (CAST(:canonical_id AS uuid), CAST(:duplicate_id AS uuid)) "
                "ORDER BY id"
            ),
            {
                "canonical_id": CANONICAL_DOCUMENT_ID,
                "duplicate_id": DUPLICATE_DOCUMENT_ID,
            },
        )
    ).all()
    expected = [
        (CANONICAL_DOCUMENT_ID, "ready", True),
        (DUPLICATE_DOCUMENT_ID, "ready", True),
    ]
    if [tuple(row) for row in rows] != expected:
        raise RuntimeError(f"Downgrade did not restore legacy documents: {rows!r}")


async def seed_legacy_finding(connection: AsyncConnection) -> None:
    """Insert a pre-0004 finding to prove lossless legacy backfill."""

    await _require_revision(connection, PHASE3_REVISION)
    await connection.execute(
        text(
            "INSERT INTO workflow_runs "
            "(requested_by_id, question, document_ids, idempotency_key, request_hash, "
            " origin_correlation_id, state, intent, answer_text, insufficient_evidence, "
            " cited_chunk_ids, error_code, error_detail, id, created_at, updated_at) "
            "VALUES (CAST(:user_id AS uuid), 'Legacy finding migration probe', "
            "CAST('[]' AS json), 'legacy-finding-migration-probe', :request_hash, "
            "'legacy-finding-migration-probe', 'running', 'structured_extraction', "
            "'Legacy finding', false, CAST('[]' AS json), NULL, NULL, "
            "CAST(:workflow_id AS uuid), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {
            "user_id": LEGACY_USER_ID,
            "workflow_id": FINDING_WORKFLOW_ID,
            "request_hash": "d" * 64,
        },
    )
    await connection.execute(
        text(
            "INSERT INTO extracted_findings "
            "(workflow_run_id, finding_type, summary, normalized_value, "
            " responsible_party, due_date, severity, cited_chunk_ids, stable_hash, "
            " id, created_at, updated_at) "
            "VALUES (CAST(:workflow_id AS uuid), 'obligation', 'Legacy finding survives', "
            " 'legacy_value', 'Legacy owner', NULL, NULL, CAST('[]' AS json), "
            " :stable_hash, CAST(:finding_id AS uuid), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {
            "workflow_id": FINDING_WORKFLOW_ID,
            "finding_id": LEGACY_FINDING_ID,
            "stable_hash": "e" * 64,
        },
    )


async def assert_legacy_finding_backfilled(connection: AsyncConnection) -> None:
    await _require_revision(connection, HEAD_REVISION)
    row = (
        await connection.execute(
            text(
                "SELECT summary, origin, cited_marker_ids::text, fields::text, "
                "normalizer_version, source_marker_sha256, derivation_reason "
                "FROM extracted_findings WHERE id = CAST(:finding_id AS uuid)"
            ),
            {"finding_id": LEGACY_FINDING_ID},
        )
    ).one_or_none()
    expected = ("Legacy finding survives", "model", "[]", "{}", None, None, None)
    if row is None or tuple(row) != expected:
        raise RuntimeError(f"Legacy finding backfill changed evidence semantics: {row!r}")


async def seed_derived_finding(connection: AsyncConnection) -> None:
    """Insert evidence-bearing v2 metadata that must block a lossy downgrade."""

    await _require_revision(connection, HEAD_REVISION)
    await connection.execute(
        text(
            "INSERT INTO extracted_findings "
            "(workflow_run_id, finding_type, summary, normalized_value, "
            " responsible_party, due_date, severity, cited_chunk_ids, cited_marker_ids, "
            " fields, origin, normalizer_version, source_marker_sha256, derivation_reason, "
            " stable_hash, id, created_at, updated_at) "
            "VALUES (CAST(:workflow_id AS uuid), 'obligation', 'disable vendor account', "
            " '1_hour_after_offboarding_notice_received', 'Service Desk', NULL, NULL, "
            " CAST(:chunk_ids AS json), CAST(:marker_ids AS json), CAST(:fields AS json), "
            " 'deterministic_evidence_normalizer', 'structured-obligation-binding-v2', "
            " :marker_hash, 'evidence_binding_confirmed', :stable_hash, "
            " CAST(:finding_id AS uuid), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {
            "workflow_id": FINDING_WORKFLOW_ID,
            "chunk_ids": '["' + "1" * 64 + '"]',
            "marker_ids": '["LG-POL-001:L010"]',
            "fields": (
                '{"actor":"Service Desk","action":"disable vendor account",'
                '"deadline":"1_hour_after_offboarding_notice_received"}'
            ),
            "marker_hash": "2" * 64,
            "stable_hash": "3" * 64,
            "finding_id": DERIVED_FINDING_ID,
        },
    )


async def assert_derived_finding_preserved(connection: AsyncConnection) -> None:
    await _require_revision(connection, HEAD_REVISION)
    row = (
        await connection.execute(
            text(
                "SELECT origin, normalizer_version, source_marker_sha256, "
                "derivation_reason, fields ->> 'deadline', cited_marker_ids ->> 0 "
                "FROM extracted_findings WHERE id = CAST(:finding_id AS uuid)"
            ),
            {"finding_id": DERIVED_FINDING_ID},
        )
    ).one_or_none()
    expected = (
        "deterministic_evidence_normalizer",
        "structured-obligation-binding-v2",
        "2" * 64,
        "evidence_binding_confirmed",
        "1_hour_after_offboarding_notice_received",
        "LG-POL-001:L010",
    )
    if row is None or tuple(row) != expected:
        raise RuntimeError(f"Blocked downgrade did not preserve finding evidence: {row!r}")


async def cleanup_derived_finding(connection: AsyncConnection) -> None:
    await _require_revision(connection, HEAD_REVISION)
    await connection.execute(
        text("DELETE FROM extracted_findings WHERE id = CAST(:finding_id AS uuid)"),
        {"finding_id": DERIVED_FINDING_ID},
    )


async def seed_orphan_citation(connection: AsyncConnection) -> None:
    await _require_revision(connection, HEAD_REVISION)
    await connection.execute(
        text(
            "INSERT INTO question_jobs "
            "(requested_by_id, question, document_ids, idempotency_key, state, "
            " error_code, error_detail, started_at, completed_at, id, created_at, "
            " updated_at, request_hash, origin_correlation_id) "
            "VALUES (CAST(:user_id AS uuid), 'Migration orphan citation probe', "
            " CAST(:document_ids AS json), 'migration-orphan-citation', 'succeeded', "
            " NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CAST(:job_id AS uuid), "
            " CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :request_hash, "
            " 'migration-orphan-citation')"
        ),
        {
            "user_id": LEGACY_USER_ID,
            "document_ids": f'["{CANONICAL_DOCUMENT_ID}"]',
            "job_id": ORPHAN_QUESTION_ID,
            "request_hash": "c" * 64,
        },
    )
    await connection.execute(
        text(
            "INSERT INTO answers "
            "(question_job_id, text, insufficient_evidence, model_name, prompt_version, "
            " retrieval_ms, generation_ms, created_at, id) "
            "VALUES (CAST(:job_id AS uuid), 'Preserved citation answer', false, "
            " 'migration-probe', 'migration-probe', 1, 1, CURRENT_TIMESTAMP, "
            " CAST(:answer_id AS uuid))"
        ),
        {"job_id": ORPHAN_QUESTION_ID, "answer_id": ORPHAN_ANSWER_ID},
    )
    await connection.execute(
        text(
            "INSERT INTO citations "
            "(answer_id, chunk_id, ordinal, quote, document_id, revision_id, "
            " anchor_key, anchor_label, start_offset, end_offset, id) "
            "VALUES (CAST(:answer_id AS uuid), NULL, 1, 'Preserved snapshot', "
            " CAST(:document_id AS uuid), CAST(:revision_id AS uuid), "
            " 'migration:orphan', 'Migration orphan', 0, 18, CAST(:citation_id AS uuid))"
        ),
        {
            "answer_id": ORPHAN_ANSWER_ID,
            "document_id": CANONICAL_DOCUMENT_ID,
            "revision_id": CANONICAL_REVISION_ID,
            "citation_id": ORPHAN_CITATION_ID,
        },
    )


async def assert_orphan_citation_preserved(connection: AsyncConnection) -> None:
    await _require_revision(connection, HEAD_REVISION)
    row = (
        await connection.execute(
            text(
                "SELECT quote, chunk_id IS NULL FROM citations "
                "WHERE id = CAST(:citation_id AS uuid)"
            ),
            {"citation_id": ORPHAN_CITATION_ID},
        )
    ).one_or_none()
    if row is None or tuple(row) != ("Preserved snapshot", True):
        raise RuntimeError(f"Blocked downgrade did not preserve the citation: {row!r}")


async def cleanup_orphan_citation_probe(connection: AsyncConnection) -> None:
    await _require_revision(connection, HEAD_REVISION)
    await connection.execute(
        text("DELETE FROM question_jobs WHERE id = CAST(:job_id AS uuid)"),
        {"job_id": ORPHAN_QUESTION_ID},
    )


async def simulate_historical_phase2(connection: AsyncConnection) -> None:
    await _require_revision(connection, PHASE2_REVISION)
    await connection.execute(
        text(
            "UPDATE documents SET current_revision_id = NULL "
            "WHERE id IN (CAST(:canonical_id AS uuid), CAST(:duplicate_id AS uuid))"
        ),
        {
            "canonical_id": CANONICAL_DOCUMENT_ID,
            "duplicate_id": DUPLICATE_DOCUMENT_ID,
        },
    )
    await connection.execute(
        text(
            "DELETE FROM documents "
            "WHERE id IN (CAST(:canonical_id AS uuid), CAST(:duplicate_id AS uuid))"
        ),
        {
            "canonical_id": CANONICAL_DOCUMENT_ID,
            "duplicate_id": DUPLICATE_DOCUMENT_ID,
        },
    )
    await connection.execute(
        text("DELETE FROM users WHERE id = CAST(:user_id AS uuid)"),
        {"user_id": LEGACY_USER_ID},
    )
    await connection.execute(
        text(
            "INSERT INTO users "
            "(username, display_name, password_hash, role, is_active, id, created_at, updated_at) "
            "VALUES ('migration-historical-user', 'Migration Historical User', "
            "'not-a-login-password-hash', 'admin', true, CAST(:user_id AS uuid), "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {"user_id": HISTORICAL_USER_ID},
    )
    await connection.execute(
        text(
            "INSERT INTO workflow_runs "
            "(requested_by_id, question, document_ids, idempotency_key, request_hash, "
            " origin_correlation_id, state, intent, answer_text, insufficient_evidence, "
            " cited_chunk_ids, error_code, error_detail, id, created_at, updated_at) "
            "VALUES (CAST(:user_id AS uuid), 'Historical workflow', CAST('[]' AS json), "
            " 'historical-before-repair', :request_hash, 'migration-historical-c57', "
            " 'running', NULL, NULL, NULL, CAST('[]' AS json), NULL, NULL, "
            " CAST(:workflow_id AS uuid), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {
            "user_id": HISTORICAL_USER_ID,
            "workflow_id": HISTORICAL_WORKFLOW_ID,
            "request_hash": "b" * 64,
        },
    )
    await connection.execute(
        text("ALTER TABLE workflow_runs DROP CONSTRAINT IF EXISTS uq_workflow_run_idempotency")
    )
    await connection.execute(text("ALTER TABLE workflow_runs DROP COLUMN idempotency_key"))
    await connection.execute(text("DROP INDEX IF EXISTS uq_document_actor_content_active"))
    await connection.execute(
        text(
            "ALTER TABLE documents ADD CONSTRAINT uq_document_actor_content "
            "UNIQUE (created_by_id, source_content_sha256)"
        )
    )
    await connection.execute(
        text(
            "ALTER TABLE outbox_events ADD CONSTRAINT legacy_outbox_state_check "
            "CHECK (state IN ('pending', 'dispatched'))"
        )
    )


async def assert_reconciled(connection: AsyncConnection) -> None:
    await _require_revision(connection, HEAD_REVISION)
    idempotency_key = await connection.scalar(
        text("SELECT idempotency_key FROM workflow_runs WHERE id = CAST(:workflow_id AS uuid)"),
        {"workflow_id": HISTORICAL_WORKFLOW_ID},
    )
    if not isinstance(idempotency_key, str) or not idempotency_key.startswith("legacy-"):
        raise RuntimeError("Historical workflow idempotency key was not backfilled")

    names = set(
        (
            await connection.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename = 'documents' "
                    "AND indexname IN "
                    "('uq_document_actor_content', 'uq_document_actor_content_active')"
                )
            )
        ).scalars()
    )
    if names != {"uq_document_actor_content_active"}:
        raise RuntimeError(f"Historical document uniqueness was not reconciled: {names!r}")

    workflow_constraint = await connection.scalar(
        text(
            "SELECT count(*) FROM pg_constraint "
            "WHERE conrelid = 'workflow_runs'::regclass "
            "AND conname = 'uq_workflow_run_idempotency'"
        )
    )
    legacy_state_check = await connection.scalar(
        text(
            "SELECT count(*) FROM pg_constraint "
            "WHERE conrelid = 'outbox_events'::regclass "
            "AND conname = 'legacy_outbox_state_check'"
        )
    )
    if workflow_constraint != 1 or legacy_state_check != 0:
        raise RuntimeError("Historical workflow/outbox constraints were not reconciled")


COMMANDS: dict[str, Callable[[AsyncConnection], Awaitable[None]]] = {
    "seed-legacy-duplicates": seed_legacy_duplicates,
    "assert-quarantined": assert_quarantined,
    "assert-restored": assert_restored,
    "seed-legacy-finding": seed_legacy_finding,
    "assert-legacy-finding-backfilled": assert_legacy_finding_backfilled,
    "seed-derived-finding": seed_derived_finding,
    "assert-derived-finding-preserved": assert_derived_finding_preserved,
    "cleanup-derived-finding": cleanup_derived_finding,
    "seed-orphan-citation": seed_orphan_citation,
    "assert-orphan-citation-preserved": assert_orphan_citation_preserved,
    "cleanup-orphan-citation-probe": cleanup_orphan_citation_probe,
    "simulate-historical-phase2": simulate_historical_phase2,
    "assert-reconciled": assert_reconciled,
}


async def _run(command: str) -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await COMMANDS[command](connection)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=sorted(COMMANDS))
    arguments = parser.parse_args()
    asyncio.run(_run(arguments.command))
    print(f"Migration data probe passed: {arguments.command}")


if __name__ == "__main__":
    main()
