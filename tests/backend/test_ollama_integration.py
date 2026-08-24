"""Opt-in locked-Ollama ingestion proof against a disposable PostgreSQL database."""

from __future__ import annotations

import io
import math
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import UploadFile
from localguard_api.config import Settings
from localguard_api.database import Database
from localguard_api.ingestion import PrivateUploadStore, validate_upload
from localguard_api.middleware import correlation_id_var
from localguard_api.models import Chunk, DocumentRevision, DocumentState, Role, User
from localguard_api.providers import Evidence, OllamaProvider, RuntimeLease
from localguard_api.retrieval import HybridRetriever
from localguard_api.security import hash_password
from localguard_api.services import DocumentService, IngestionProcessor
from redis.asyncio import Redis
from sqlalchemy import select
from starlette.datastructures import Headers

pytestmark = [
    pytest.mark.integration,
    pytest.mark.real_model,
    pytest.mark.skipif(
        os.getenv("RUN_DB_INTEGRATION") != "1"
        or os.getenv("RUN_REAL_MODEL_TESTS") != "1"
        or os.getenv("LOCALGUARD_DISPOSABLE_DB") != "1",
        reason=(
            "requires RUN_DB_INTEGRATION=1, RUN_REAL_MODEL_TESTS=1, and LOCALGUARD_DISPOSABLE_DB=1"
        ),
    ),
]

ROOT = Path(__file__).resolve().parents[2]
DEMO_FIXTURE = ROOT / "fixtures" / "documents" / "clean" / "lg-pol-001-vendor-access.pdf"
DEMO_QUESTION = (
    "How long does the Service Desk have to disable a vendor account after it receives "
    "an offboarding notice?"
)
DEMO_ACTION = (
    "An authorized sponsor's vendor offboarding notice was received at "
    "2026-09-01T09:00:00Z. Propose the required account-disable task; do not execute "
    "it without review."
)


@pytest.mark.asyncio
async def test_locked_ollama_ingests_full_demo_fixture(tmp_path: Path) -> None:
    settings = Settings(
        app_env="test",
        ai_provider="ollama",
        embedding_provider="ollama",
        allowed_hosts=("testserver",),
        upload_root=tmp_path / "uploads",
    )
    database = Database(settings)
    redis = Redis.from_url(settings.redis_url)
    provider = OllamaProvider(
        settings,
        RuntimeLease(redis, settings.model_lock_ttl_seconds),
    )
    store = PrivateUploadStore(settings.upload_root)
    reviewer = User(
        username=f"ollama-ingestion-{uuid.uuid4().hex}",
        display_name="Ollama ingestion probe",
        password_hash=hash_password("ollama ingestion probe password"),
        role=Role.REVIEWER,
    )
    raw = DEMO_FIXTURE.read_bytes()
    upload = UploadFile(
        file=io.BytesIO(raw),
        filename=DEMO_FIXTURE.name,
        headers=Headers({"content-type": "application/pdf"}),
    )
    token = correlation_id_var.set(f"ollama-ingestion-{uuid.uuid4().hex}")
    try:
        async with database.sessions() as db:
            db.add(reviewer)
            await db.commit()
        validated = await validate_upload(upload, settings)
        async with database.sessions() as db:
            accepted = await DocumentService(settings, store).accept(db, validated, reviewer)
        assert not accepted.duplicate

        async with database.sessions() as db:
            processed = await IngestionProcessor(settings, store, provider).process(
                db, accepted.revision.id
            )
        assert processed

        async with database.sessions() as db:
            revision = await db.get(DocumentRevision, accepted.revision.id)
            chunks = list(
                (
                    await db.scalars(
                        select(Chunk)
                        .where(Chunk.revision_id == accepted.revision.id)
                        .order_by(Chunk.ordinal)
                    )
                )
                .unique()
                .all()
            )
        assert revision is not None and revision.state == DocumentState.READY
        assert [len(chunk.content) for chunk in chunks] == [1084, 889]
        assert all(chunk.embedding is not None for chunk in chunks)
        assert all(len(chunk.embedding or []) == 384 for chunk in chunks)
        assert all(
            math.sqrt(sum(value * value for value in chunk.embedding or []))
            == pytest.approx(1.0, abs=1e-6)
            for chunk in chunks
        )

        async with database.sessions() as db:
            retrieval = await HybridRetriever(settings, provider).search(
                db, DEMO_QUESTION, [accepted.document.id]
            )
            assert retrieval.sufficient
            evidence = [
                Evidence(
                    chunk_id=item.chunk.stable_id,
                    document_title=item.chunk.revision.document.title,
                    anchor_label=item.chunk.anchor.label,
                    content=item.chunk.content,
                    source_id="LG-POL-001",
                    marker_ids=tuple(
                        dict.fromkeys(re.findall(r"LG-POL-001:L\d{3}", item.chunk.content))
                    ),
                )
                for item in retrieval.chunks
            ]
        answer = await provider.answer(DEMO_QUESTION, evidence)
        evidence_by_id = {item.chunk_id: item for item in evidence}
        assert not answer.insufficient_evidence
        assert answer.cited_chunk_ids
        assert set(answer.cited_chunk_ids).issubset(evidence_by_id)
        assert any(
            "LG-POL-001:L010" in evidence_by_id[identifier].content
            for identifier in answer.cited_chunk_ids
        )
        assert "one hour" in answer.answer.casefold()

        workflow = await provider.analyze(DEMO_ACTION, evidence, action_requested=True)
        assert not workflow.insufficient_evidence
        assert len(workflow.claims) == 1
        claim = workflow.claims[0]
        assert claim.predicate == "vendor_account_disable_deadline"
        assert claim.normalized_value == "1_hour_after_offboarding_notice_received"
        assert claim.cited_marker_ids == ["LG-POL-001:L010"]
        assert workflow.proposed_task is not None
        assert set(workflow.cited_chunk_ids).issubset(evidence_by_id)
        assert set(workflow.proposed_task.cited_chunk_ids).issubset(evidence_by_id)
        assert "LG-POL-001:L010" in workflow.proposed_task.cited_marker_ids
        assert workflow.proposed_task.assignee == "Service Desk"
        assert workflow.proposed_task.priority.value == "high"
        assert workflow.proposed_task.due_at == datetime(2026, 9, 1, 10, tzinfo=UTC)
    finally:
        correlation_id_var.reset(token)
        await upload.close()
        await provider.close()
        await redis.aclose()
        await database.close()
