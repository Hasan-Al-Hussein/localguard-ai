"""Real-PostgreSQL evaluator corpus-identity regressions."""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path
from typing import cast

import pytest
from localguard_api.agent.evaluation_adapter import (
    ApplicationEvaluationSystem,
    _SourceFixture,
    build_evaluation_system,
)
from localguard_api.models import Document, DocumentRevision, DocumentState, Role
from sqlalchemy import select

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_INTEGRATION") != "1",
        reason="set RUN_DB_INTEGRATION=1 inside the local Compose network",
    ),
]

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_same_filename_wrong_digest_is_not_reused_and_exact_fixture_is_ingested(
    tmp_path: Path,
) -> None:
    system = cast(
        ApplicationEvaluationSystem,
        build_evaluation_system(provider="deterministic", repository_root=ROOT),
    )
    source_id = f"TEST-{uuid.uuid4().hex}"
    fixture = tmp_path / f"same-name-{uuid.uuid4().hex}.txt"
    content = (
        f"[LG-POL-999:L001] The Records Owner must review {source_id} within one business "
        "day after receiving it.\n"
    ).encode()
    fixture.write_bytes(content)
    expected_digest = hashlib.sha256(content).hexdigest()
    wrong_content = f"wrong same-name document {source_id}".encode()
    wrong_digest = hashlib.sha256(wrong_content).hexdigest()
    system.source_manifest[source_id] = _SourceFixture(fixture, expected_digest)

    try:
        admin = await system._get_actor(Role.ADMIN)
        async with system.database.sessions() as db:
            wrong_document = Document(
                title="Wrong same-name fixture",
                created_by_id=admin.id,
                source_content_sha256=wrong_digest,
                state=DocumentState.READY,
            )
            db.add(wrong_document)
            await db.flush()
            wrong_revision = DocumentRevision(
                document_id=wrong_document.id,
                revision_number=1,
                original_filename=fixture.name,
                media_type="text/plain",
                storage_key=f"{uuid.uuid4().hex}.txt",
                content_sha256=wrong_digest,
                byte_size=len(wrong_content),
                state=DocumentState.READY,
                extracted_characters=24,
                anchor_count=1,
                origin_correlation_id=f"eval-wrong-{uuid.uuid4().hex}",
            )
            db.add(wrong_revision)
            await db.flush()
            wrong_document.current_revision_id = wrong_revision.id
            await db.commit()
            wrong_document_id = wrong_document.id

        assert await system._find_ready_document(expected_digest) is None
        document_ids = await system._ensure_documents([source_id])

        assert len(document_ids) == 1
        assert document_ids[0] != wrong_document_id
        async with system.database.sessions() as db:
            selected = await db.scalar(
                select(DocumentRevision)
                .join(Document, Document.current_revision_id == DocumentRevision.id)
                .where(Document.id == document_ids[0])
            )
        assert selected is not None
        assert selected.original_filename == fixture.name
        assert selected.content_sha256 == expected_digest
        assert selected.state == DocumentState.READY
    finally:
        await system.aclose()


@pytest.mark.asyncio
async def test_exact_digest_ready_document_is_reused_independent_of_filename(
    tmp_path: Path,
) -> None:
    system = cast(
        ApplicationEvaluationSystem,
        build_evaluation_system(provider="deterministic", repository_root=ROOT),
    )
    source_id = f"TEST-{uuid.uuid4().hex}"
    fixture = tmp_path / f"manifest-name-{uuid.uuid4().hex}.txt"
    content = (
        f"[LG-POL-999:L001] The Records Owner must review {source_id} within one business "
        "day after receiving it.\n"
    ).encode()
    fixture.write_bytes(content)
    expected_digest = hashlib.sha256(content).hexdigest()
    system.source_manifest[source_id] = _SourceFixture(fixture, expected_digest)

    try:
        admin = await system._get_actor(Role.ADMIN)
        async with system.database.sessions() as db:
            exact_document = Document(
                title="Exact fixture under a renamed upload",
                created_by_id=admin.id,
                source_content_sha256=expected_digest,
                state=DocumentState.READY,
            )
            db.add(exact_document)
            await db.flush()
            exact_revision = DocumentRevision(
                document_id=exact_document.id,
                revision_number=1,
                original_filename=f"renamed-{uuid.uuid4().hex}.txt",
                media_type="text/plain",
                storage_key=f"{uuid.uuid4().hex}.txt",
                content_sha256=expected_digest,
                byte_size=len(content),
                state=DocumentState.READY,
                extracted_characters=len(content),
                anchor_count=1,
                origin_correlation_id=f"eval-exact-{uuid.uuid4().hex}",
            )
            db.add(exact_revision)
            await db.flush()
            exact_document.current_revision_id = exact_revision.id
            await db.commit()
            exact_document_id = exact_document.id

        document_ids = await system._ensure_documents([source_id])

        assert document_ids == [exact_document_id]
    finally:
        await system.aclose()
