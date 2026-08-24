"""Opt-in real PostgreSQL/pgvector and API-session integration proofs."""

from __future__ import annotations

import json
import os
import uuid
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
import typer
from localguard_api.agent.checkpoints import setup_postgres_checkpoints
from localguard_api.cli import (
    _CHECKPOINT_PURGE_CONFIRMATION,
    _export_orphan_citations,
    _purge_checkpoint_history,
    _purge_orphan_citations,
    _seed_all,
    _sync_mcp_bootstrap_token,
    _upsert_user,
)
from localguard_api.config import Settings
from localguard_api.database import Database
from localguard_api.main import create_app
from localguard_api.models import (
    Answer,
    AuditEvent,
    Chunk,
    Citation,
    Document,
    DocumentRevision,
    DocumentState,
    JobState,
    MCPAccessToken,
    QuestionJob,
    Role,
    SessionToken,
    SourceAnchor,
    User,
    utc_now,
)
from localguard_api.providers import DeterministicProvider
from localguard_api.retrieval import HybridRetriever
from localguard_api.security import hash_password, token_digest, verify_password
from pydantic import SecretStr
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_INTEGRATION") != "1",
        reason="set RUN_DB_INTEGRATION=1 inside the local Compose network",
    ),
]


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        allow_test_providers=True,
        ai_provider="deterministic",
        embedding_provider="deterministic",
        allowed_hosts=("testserver",),
        upload_root=tmp_path / "uploads",
    )


@pytest.mark.asyncio
async def test_pgvector_and_full_text_rrf_return_current_revision(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    provider = DeterministicProvider()
    async with database.engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            user = User(
                id=uuid.uuid4(),
                username=f"retrieval-{uuid.uuid4().hex}",
                display_name="Retrieval Test",
                password_hash=hash_password("integration password is sufficiently long"),
                role=Role.VIEWER,
            )
            document = Document(
                id=uuid.uuid4(),
                title="Retention Policy",
                created_by_id=user.id,
                source_content_sha256="1" * 64,
                state=DocumentState.READY,
            )
            session.add(user)
            await session.flush()
            session.add(document)
            await session.flush()
            revision = DocumentRevision(
                id=uuid.uuid4(),
                document_id=document.id,
                revision_number=1,
                original_filename="retention.txt",
                media_type="text/plain",
                storage_key=f"{uuid.uuid4().hex}.txt",
                content_sha256="1" * 64,
                byte_size=64,
                state=DocumentState.READY,
                origin_correlation_id="integration-retrieval",
            )
            session.add(revision)
            await session.flush()
            document.current_revision_id = revision.id
            anchor = SourceAnchor(
                id=uuid.uuid4(),
                revision_id=revision.id,
                stable_key="lines:1-1",
                kind="text_lines",
                label="Lines 1-1",
                ordinal=1,
                start_offset=0,
                end_offset=53,
                text="Records must be retained for seven years after closure.",
            )
            embedding = (await provider.embed(["How long must records be retained?"]))[0]
            chunk = Chunk(
                id=uuid.uuid4(),
                revision_id=revision.id,
                anchor_id=anchor.id,
                stable_id="a" * 64,
                ordinal=1,
                start_offset=0,
                end_offset=len(anchor.text),
                content=anchor.text,
                content_sha256="2" * 64,
                embedding=embedding,
            )
            session.add_all([anchor, chunk])
            await session.flush()

            result = await HybridRetriever(settings, provider).search(
                session, "How long must records be retained?", [document.id]
            )
            assert result.sufficient
            assert result.chunks[0].chunk.stable_id == "a" * 64
            assert result.chunks[0].vector_rank == 1

            irrelevant_settings = settings.model_copy(
                update={
                    "retrieval_min_vector_similarity": 0.999999,
                    "retrieval_min_text_score": 0.999999,
                }
            )
            irrelevant = await HybridRetriever(irrelevant_settings, provider).search(
                session,
                "quantum cafeteria menu asteroid permit",
                [document.id],
            )
            assert irrelevant.chunks
            assert not irrelevant.sufficient
        finally:
            await session.close()
            await transaction.rollback()
    await database.close()


@pytest.mark.asyncio
async def test_cookie_session_csrf_and_logout_against_postgres(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    username = f"api-{uuid.uuid4().hex}"
    password = "integration password is sufficiently long"
    user_id = uuid.uuid4()
    database = Database(settings)
    async with database.sessions() as session:
        session.add(
            User(
                id=user_id,
                username=username,
                display_name="API Integration",
                password_hash=hash_password(password),
                role=Role.REVIEWER,
            )
        )
        await session.commit()

    try:
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                login = await client.post(
                    "/auth/login", json={"username": username, "password": password}
                )
                assert login.status_code == 200
                csrf = login.json()["csrf_token"]
                assert settings.session_cookie_name in client.cookies
                me = await client.get("/auth/me")
                assert me.status_code == 200
                assert me.json()["role"] == "reviewer"
                logout = await client.post(
                    "/auth/logout", headers={settings.csrf_header_name: csrf}
                )
                assert logout.status_code == 200
                assert settings.session_cookie_name not in client.cookies
    finally:
        async with database.sessions() as session:
            await session.execute(delete(AuditEvent).where(AuditEvent.actor_id == user_id))
            await session.execute(delete(SessionToken).where(SessionToken.user_id == user_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await database.close()


@pytest.mark.asyncio
async def test_upsert_existing_user_revokes_only_that_users_active_sessions(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    target_id = uuid.uuid4()
    unrelated_id = uuid.uuid4()
    target_username = f"seed-target-{uuid.uuid4().hex}"
    unrelated_username = f"seed-unrelated-{uuid.uuid4().hex}"
    now = utc_now()

    def active_session(user_id: uuid.UUID) -> SessionToken:
        return SessionToken(
            user_id=user_id,
            token_hash=uuid.uuid4().bytes + uuid.uuid4().bytes,
            csrf_hash=uuid.uuid4().bytes + uuid.uuid4().bytes,
            created_at=now,
            expires_at=now + timedelta(hours=1),
            last_seen_at=now,
        )

    async with database.sessions() as session:
        session.add_all(
            [
                User(
                    id=target_id,
                    username=target_username,
                    display_name="Seed Target",
                    password_hash=hash_password("old target password"),
                    role=Role.VIEWER,
                ),
                User(
                    id=unrelated_id,
                    username=unrelated_username,
                    display_name="Unrelated User",
                    password_hash=hash_password("unrelated password"),
                    role=Role.VIEWER,
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                active_session(target_id),
                active_session(target_id),
                active_session(unrelated_id),
            ]
        )
        await session.commit()

    try:
        new_password = "rotated target password"
        await _upsert_user(
            database,
            target_username,
            "Updated Seed Target",
            Role.REVIEWER,
            new_password,
        )

        async with database.sessions() as session:
            target = await session.get(User, target_id)
            target_sessions = list(
                (
                    await session.scalars(
                        select(SessionToken).where(SessionToken.user_id == target_id)
                    )
                ).all()
            )
            unrelated_sessions = list(
                (
                    await session.scalars(
                        select(SessionToken).where(SessionToken.user_id == unrelated_id)
                    )
                ).all()
            )
        assert target is not None
        assert target.display_name == "Updated Seed Target"
        assert target.role == Role.REVIEWER
        assert verify_password(new_password, target.password_hash)
        assert len(target_sessions) == 2
        assert all(item.revoked_at is not None for item in target_sessions)
        assert len(unrelated_sessions) == 1
        assert unrelated_sessions[0].revoked_at is None
    finally:
        async with database.sessions() as session:
            await session.execute(
                delete(SessionToken).where(SessionToken.user_id.in_([target_id, unrelated_id]))
            )
            await session.execute(delete(User).where(User.id.in_([target_id, unrelated_id])))
            await session.commit()
        await database.close()


@pytest.mark.asyncio
async def test_checkpoint_purge_requires_confirmation_and_preserves_migrations(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    await setup_postgres_checkpoints(settings)
    database = Database(settings)
    thread_id = f"purge-regression-{uuid.uuid4()}"
    checkpoint_id = uuid.uuid4().hex
    async with database.sessions() as session:
        migrations_before = int(
            await session.scalar(text("SELECT count(*) FROM checkpoint_migrations")) or 0
        )
        await session.execute(
            text(
                "INSERT INTO checkpoints "
                "(thread_id, checkpoint_ns, checkpoint_id, type, checkpoint, metadata) "
                "VALUES (:thread_id, '', :checkpoint_id, 'json', "
                "CAST(:checkpoint AS jsonb), '{}'::jsonb)"
            ),
            {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
                "checkpoint": '{"private":"checkpoint purge regression"}',
            },
        )
        await session.execute(
            text(
                "INSERT INTO checkpoint_blobs "
                "(thread_id, checkpoint_ns, channel, version, type, blob) "
                "VALUES (:thread_id, '', 'messages', '1', 'bytes', :blob)"
            ),
            {"thread_id": thread_id, "blob": b"private blob"},
        )
        await session.execute(
            text(
                "INSERT INTO checkpoint_writes "
                "(thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, blob) "
                "VALUES (:thread_id, '', :checkpoint_id, 'task', 0, "
                "'messages', 'bytes', :blob)"
            ),
            {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
                "blob": b"private write",
            },
        )
        await session.commit()

    try:
        with pytest.raises(typer.BadParameter):
            await _purge_checkpoint_history(settings, confirmation="PURGE")
        async with database.sessions() as session:
            retained = int(
                await session.scalar(
                    text("SELECT count(*) FROM checkpoints WHERE thread_id = :thread_id"),
                    {"thread_id": thread_id},
                )
                or 0
            )
        assert retained == 1

        counts = await _purge_checkpoint_history(
            settings,
            confirmation=_CHECKPOINT_PURGE_CONFIRMATION,
        )
        assert counts["checkpoints"] >= 1
        assert counts["checkpoint_blobs"] >= 1
        assert counts["checkpoint_writes"] >= 1
        async with database.sessions() as session:
            history_counts = {
                "checkpoints": int(
                    await session.scalar(text("SELECT count(*) FROM checkpoints")) or 0
                ),
                "checkpoint_blobs": int(
                    await session.scalar(text("SELECT count(*) FROM checkpoint_blobs")) or 0
                ),
                "checkpoint_writes": int(
                    await session.scalar(text("SELECT count(*) FROM checkpoint_writes")) or 0
                ),
            }
            migrations_after = int(
                await session.scalar(text("SELECT count(*) FROM checkpoint_migrations")) or 0
            )
            schema_tables = int(
                await session.scalar(
                    text(
                        "SELECT count(*) FROM pg_class "
                        "WHERE relname IN ('checkpoints', 'checkpoint_blobs', "
                        "'checkpoint_writes', 'checkpoint_migrations')"
                    )
                )
                or 0
            )
        assert history_counts == {
            "checkpoints": 0,
            "checkpoint_blobs": 0,
            "checkpoint_writes": 0,
        }
        assert migrations_before > 0
        assert migrations_after == migrations_before
        assert schema_tables == 4
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_bootstrap_mcp_token_rotation_revokes_old_and_sets_finite_expiry(
    tmp_path: Path,
) -> None:
    first_raw = f"first-{uuid.uuid4().hex}"
    second_raw = f"second-{uuid.uuid4().hex}"
    unrelated_raw = f"unrelated-{uuid.uuid4().hex}"
    shared = {
        "bootstrap_admin_password": SecretStr("bootstrap admin password"),
        "bootstrap_reviewer_password": SecretStr("bootstrap reviewer password"),
        "bootstrap_viewer_password": SecretStr("bootstrap viewer password"),
    }
    first_settings = _settings(tmp_path).model_copy(
        update={
            **shared,
            "mcp_bootstrap_token": SecretStr(first_raw),
            "mcp_bootstrap_token_ttl_days": 7,
        }
    )
    await _seed_all(first_settings)
    database = Database(first_settings)
    first_digest = token_digest(first_raw)
    second_digest = token_digest(second_raw)
    unrelated_digest = token_digest(unrelated_raw)
    session_digest = token_digest(f"session-{uuid.uuid4().hex}")
    try:
        async with database.sessions() as session:
            first = await session.scalar(
                select(MCPAccessToken).where(MCPAccessToken.token_hash == first_digest)
            )
            admin = await session.scalar(select(User).where(User.username == "demo-admin"))
            assert first is not None and first.expires_at is not None
            assert admin is not None
            first_remaining = first.expires_at - utc_now()
            assert timedelta(days=6, hours=23) < first_remaining <= timedelta(days=7)
            session.add(
                MCPAccessToken(
                    token_hash=unrelated_digest,
                    user_id=admin.id,
                    label="unrelated-automation",
                    expires_at=utc_now() + timedelta(days=90),
                )
            )
            session.add(
                SessionToken(
                    user_id=admin.id,
                    token_hash=session_digest,
                    csrf_hash=token_digest(f"csrf-{uuid.uuid4().hex}"),
                    created_at=utc_now(),
                    expires_at=utc_now() + timedelta(hours=1),
                    last_seen_at=utc_now(),
                )
            )
            await session.commit()

        second_settings = first_settings.model_copy(
            update={
                "mcp_bootstrap_token": SecretStr(second_raw),
                "mcp_bootstrap_token_ttl_days": 14,
            }
        )
        await _sync_mcp_bootstrap_token(database, second_settings)
        async with database.sessions() as session:
            first = await session.scalar(
                select(MCPAccessToken).where(MCPAccessToken.token_hash == first_digest)
            )
            second = await session.scalar(
                select(MCPAccessToken).where(MCPAccessToken.token_hash == second_digest)
            )
            unrelated = await session.scalar(
                select(MCPAccessToken).where(MCPAccessToken.token_hash == unrelated_digest)
            )
            active_session = await session.scalar(
                select(SessionToken).where(SessionToken.token_hash == session_digest)
            )
        assert first is not None and first.revoked_at is not None
        assert second is not None and second.revoked_at is None
        assert second.expires_at is not None
        second_remaining = second.expires_at - utc_now()
        assert timedelta(days=13, hours=23) < second_remaining <= timedelta(days=14)
        assert unrelated is not None and unrelated.revoked_at is None
        assert active_session is not None and active_session.revoked_at is None
    finally:
        async with database.sessions() as session:
            await session.execute(
                delete(SessionToken).where(SessionToken.token_hash == session_digest)
            )
            await session.execute(
                delete(MCPAccessToken).where(
                    MCPAccessToken.token_hash.in_([first_digest, second_digest, unrelated_digest])
                )
            )
            await session.commit()
        await database.close()


@pytest.mark.asyncio
async def test_orphan_citation_export_is_no_overwrite_and_purge_requires_confirmation(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    user_id = uuid.uuid4()
    document_id = uuid.uuid4()
    revision_id = uuid.uuid4()
    job_id = uuid.uuid4()
    answer_id = uuid.uuid4()
    citation_id = uuid.uuid4()
    async with database.sessions() as session:
        session.add(
            User(
                id=user_id,
                username=f"orphan-export-{uuid.uuid4().hex}",
                display_name="Orphan Export",
                password_hash=hash_password("orphan export password"),
                role=Role.VIEWER,
            )
        )
        await session.flush()
        document = Document(
            id=document_id,
            title="Orphan citation document",
            created_by_id=user_id,
            source_content_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
            state=DocumentState.READY,
        )
        session.add(document)
        await session.flush()
        session.add(
            DocumentRevision(
                id=revision_id,
                document_id=document_id,
                revision_number=1,
                original_filename="orphan.txt",
                media_type="text/plain",
                storage_key=f"{uuid.uuid4().hex}.txt",
                content_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
                byte_size=64,
                state=DocumentState.READY,
                origin_correlation_id="orphan-export-regression",
            )
        )
        await session.flush()
        document.current_revision_id = revision_id
        session.add(
            QuestionJob(
                id=job_id,
                requested_by_id=user_id,
                question="What did the deleted source say?",
                document_ids=[str(document_id)],
                idempotency_key=f"orphan-export-{uuid.uuid4().hex}",
                request_hash=uuid.uuid4().hex + uuid.uuid4().hex,
                origin_correlation_id="orphan-export-regression",
                state=JobState.SUCCEEDED,
                completed_at=utc_now(),
            )
        )
        await session.flush()
        session.add(
            Answer(
                id=answer_id,
                question_job_id=job_id,
                text="A retained answer.",
                insufficient_evidence=False,
                model_name="orphan-export-test",
                prompt_version="test-v1",
                retrieval_ms=1.0,
                generation_ms=1.0,
            )
        )
        await session.flush()
        session.add(
            Citation(
                id=citation_id,
                answer_id=answer_id,
                chunk_id=None,
                ordinal=1,
                quote="Sensitive immutable citation snapshot.",
                document_id=document_id,
                revision_id=revision_id,
                anchor_key="lines:1-1",
                anchor_label="Lines 1-1",
                start_offset=0,
                end_offset=38,
            )
        )
        await session.commit()

    output = tmp_path / "orphan-citations.json"
    try:
        exported_path, exported_count = await _export_orphan_citations(settings, output=output)
        payload = json.loads(exported_path.read_text(encoding="utf-8"))
        assert exported_count >= 1
        assert payload["count"] == exported_count
        exported = {item["id"]: item for item in payload["citations"]}
        assert exported[str(citation_id)]["quote"] == "Sensitive immutable citation snapshot."
        with pytest.raises(FileExistsError):
            await _export_orphan_citations(settings, output=output)
        with pytest.raises(typer.BadParameter):
            await _purge_orphan_citations(settings, confirmation="PURGE")
        async with database.sessions() as session:
            retained = await session.get(Citation, citation_id)
        assert retained is not None
    finally:
        async with database.sessions() as session:
            await session.execute(delete(Citation).where(Citation.id == citation_id))
            await session.execute(delete(Answer).where(Answer.id == answer_id))
            await session.execute(delete(QuestionJob).where(QuestionJob.id == job_id))
            await session.execute(
                update(Document).where(Document.id == document_id).values(current_revision_id=None)
            )
            await session.execute(delete(Document).where(Document.id == document_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await database.close()
