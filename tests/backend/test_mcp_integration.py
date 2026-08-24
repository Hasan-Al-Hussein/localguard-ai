"""Authenticated real-PostgreSQL MCP transport regressions."""

from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from pathlib import Path
from typing import cast

import httpx
import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.utilities.tests import run_server_async
from localguard_api.agent.persistence import WorkflowRepository
from localguard_api.config import Settings
from localguard_api.database import Database
from localguard_api.main import create_app
from localguard_api.models import (
    ActionProposal,
    AuditEvent,
    Chunk,
    Document,
    DocumentRevision,
    DocumentState,
    MCPAccessToken,
    OutboxEvent,
    OutboxState,
    ProposalState,
    Role,
    SourceAnchor,
    User,
    WorkflowRun,
    WorkflowState,
    WorkflowTask,
)
from localguard_api.providers import DeterministicProvider
from localguard_api.retrieval import EvidenceResolver, HybridRetriever
from localguard_api.security import hash_password, token_digest
from localguard_mcp.auth import DatabaseTokenVerifier
from localguard_mcp.server import create_mcp_server
from localguard_mcp.tools import register_tools
from sqlalchemy import delete, func, select

pytestmark = [
    pytest.mark.integration,
    pytest.mark.security,
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
        upload_root=tmp_path / "uploads",
    )


async def _seed_actor_token_and_section(
    database: Database,
) -> tuple[str, User, Document, SourceAnchor, str]:
    raw_token = secrets.token_urlsafe(32)
    actor = User(
        username=f"mcp-integration-{uuid.uuid4().hex}",
        display_name="MCP Integration",
        password_hash=hash_password("mcp integration password"),
        role=Role.REVIEWER,
    )
    document = Document(
        title="MCP bounded section",
        created_by_id=actor.id,
        source_content_sha256=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        state=DocumentState.READY,
    )
    async with database.sessions() as db:
        db.add(actor)
        await db.flush()
        document.created_by_id = actor.id
        db.add(document)
        await db.flush()
        revision = DocumentRevision(
            document_id=document.id,
            revision_number=1,
            original_filename="bounded.txt",
            media_type="text/plain",
            storage_key=f"{uuid.uuid4().hex}.txt",
            content_sha256="c" * 64,
            byte_size=9000,
            state=DocumentState.READY,
            origin_correlation_id="mcp-section-seed",
        )
        db.add(revision)
        await db.flush()
        document.current_revision_id = revision.id
        anchor = SourceAnchor(
            revision_id=revision.id,
            stable_key="lines:1-100",
            kind="text_lines",
            label="Lines 1-100",
            ordinal=1,
            start_offset=0,
            end_offset=9000,
            text="x" * 9000,
        )
        db.add(anchor)
        await db.flush()
        chunk_content = "Vendor access must be disabled within one hour after notice."
        stable_id = hashlib.sha256(chunk_content.encode()).hexdigest()
        db.add(
            Chunk(
                revision_id=revision.id,
                anchor_id=anchor.id,
                stable_id=stable_id,
                ordinal=1,
                start_offset=0,
                end_offset=len(chunk_content),
                content=chunk_content,
                content_sha256=hashlib.sha256(chunk_content.encode()).hexdigest(),
                embedding=None,
            )
        )
        db.add(
            MCPAccessToken(
                token_hash=token_digest(raw_token),
                user_id=actor.id,
                label="mcp-integration",
            )
        )
        await db.commit()
    return raw_token, actor, document, anchor, stable_id


def _proposal_request(chunk_id: str) -> dict[str, object]:
    return {
        "request": {
            "title": "Disable vendor access",
            "description": "Disable the vendor account within one hour after notice.",
            "assignee": "Service Desk",
            "priority": "high",
            "reasoning_summary": "Bound to the cited access-control obligation.",
            "cited_chunk_ids": [chunk_id],
        }
    }


@pytest.mark.asyncio
async def test_authenticated_get_section_is_hard_bounded_with_exact_offsets(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    token, _actor, document, anchor, _chunk_id = await _seed_actor_token_and_section(database)
    server = create_mcp_server(
        settings=settings,
        database=database,
        embeddings=DeterministicProvider(),
    )
    try:
        async with run_server_async(server) as url, Client(url, auth=token) as client:
            result = await client.call_tool(
                "get_document_section",
                {
                    "request": {
                        "document_id": str(document.id),
                        "anchor_key": anchor.stable_key,
                        "offset": 100,
                        "max_chars": 8000,
                    }
                },
            )
        envelope = result.structured_content
        assert isinstance(envelope, dict)
        assert envelope["ok"] is True
        payload = envelope["data"]
        assert isinstance(payload, dict)
        assert payload["start_offset"] == 100
        assert payload["end_offset"] == 8100
        assert payload["total_characters"] == 9000
        assert payload["truncated"] is True
        assert len(payload["text"]) == 8000
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_unexpected_tool_failure_is_masked_and_audited(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    token, actor, document, anchor, _chunk_id = await _seed_actor_token_and_section(database)

    class FailingResolver:
        async def get_section(self, _db: object, _document_id: uuid.UUID, _anchor_key: str) -> None:
            raise RuntimeError("PRIVATE INTERNAL FAILURE DETAIL")

    provider = DeterministicProvider()
    server: FastMCP = FastMCP(
        "LocalGuard MCP failure test",
        auth=DatabaseTokenVerifier(database),
        mask_error_details=True,
        strict_input_validation=True,
    )
    register_tools(
        server,
        settings=settings,
        database=database,
        retriever=HybridRetriever(settings, provider),
        workflow_repository=WorkflowRepository(settings),
        resolver=cast(EvidenceResolver, FailingResolver()),
    )
    try:
        async with run_server_async(server) as url, Client(url, auth=token) as client:
            with pytest.raises(ToolError) as captured:
                await client.call_tool(
                    "get_document_section",
                    {
                        "request": {
                            "document_id": str(document.id),
                            "anchor_key": anchor.stable_key,
                        }
                    },
                )
        assert "get_document_section_failed" in str(captured.value)
        assert "PRIVATE INTERNAL" not in str(captured.value)
        async with database.sessions() as db:
            event = await db.scalar(
                select(AuditEvent)
                .where(
                    AuditEvent.actor_id == actor.id,
                    AuditEvent.action == "mcp.get_document_section",
                    AuditEvent.outcome == "failed",
                )
                .order_by(AuditEvent.occurred_at.desc())
                .limit(1)
            )
        assert event is not None
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_terminal_identical_proposal_retry_creates_fresh_pending_proposal(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    token, _actor, _document, _anchor, chunk_id = await _seed_actor_token_and_section(database)
    server = create_mcp_server(
        settings=settings,
        database=database,
        embeddings=DeterministicProvider(),
    )
    request = _proposal_request(chunk_id)
    try:
        async with run_server_async(server) as url, Client(url, auth=token) as client:
            first = await client.call_tool("propose_workflow_task", request)
            first_envelope = first.structured_content
            assert isinstance(first_envelope, dict)
            first_data = first_envelope["data"]
            assert isinstance(first_data, dict)
            first_proposal_id = uuid.UUID(str(first_data["proposal_id"]))
            first_thread_id = uuid.UUID(str(first_data["thread_id"]))

            async with database.sessions() as db:
                proposal = await db.get(ActionProposal, first_proposal_id, with_for_update=True)
                run = await db.get(WorkflowRun, first_thread_id, with_for_update=True)
                assert proposal is not None and run is not None
                proposal.state = ProposalState.REJECTED
                run.state = WorkflowState.REJECTED
                await db.commit()

            second = await client.call_tool("propose_workflow_task", request)
            second_envelope = second.structured_content
            assert isinstance(second_envelope, dict)
            second_data = second_envelope["data"]
            assert isinstance(second_data, dict)

        assert uuid.UUID(str(second_data["proposal_id"])) != first_proposal_id
        assert uuid.UUID(str(second_data["thread_id"])) != first_thread_id
        assert second_data["status"] == ProposalState.PENDING.value
        async with database.sessions() as db:
            pending_count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(ActionProposal)
                    .where(
                        ActionProposal.created_by_id == _actor.id,
                        ActionProposal.state == ProposalState.PENDING,
                    )
                )
                or 0
            )
        assert pending_count == 1
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_mcp_proposal_api_approval_executes_once_without_graph_checkpoint(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    database = Database(settings)
    token, actor, _document, _anchor, chunk_id = await _seed_actor_token_and_section(database)
    server = create_mcp_server(
        settings=settings,
        database=database,
        embeddings=DeterministicProvider(),
    )
    app = create_app(settings)
    try:
        async with run_server_async(server) as url, Client(url, auth=token) as client:
            proposed = await client.call_tool("propose_workflow_task", _proposal_request(chunk_id))
        proposal_envelope = proposed.structured_content
        assert isinstance(proposal_envelope, dict)
        proposal_data = proposal_envelope["data"]
        assert isinstance(proposal_data, dict)
        proposal_id = uuid.UUID(str(proposal_data["proposal_id"]))
        thread_id = uuid.UUID(str(proposal_data["thread_id"]))

        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://127.0.0.1",
            ) as api:
                login = await api.post(
                    "/auth/login",
                    json={
                        "username": actor.username,
                        "password": "mcp integration password",
                    },
                )
                assert login.status_code == 200
                approved = await api.post(
                    f"/approvals/{proposal_id}/approve",
                    headers={settings.csrf_header_name: login.json()["csrf_token"]},
                    json={
                        "version": proposal_data["version"],
                        "payload_hash": proposal_data["payload_hash"],
                        "evidence_snapshot_hash": proposal_data["evidence_snapshot_hash"],
                    },
                )
                assert approved.status_code == 202, approved.text
                accepted = approved.json()
                decision_id = uuid.UUID(accepted["decision"]["id"])
                outbox_event_id = uuid.UUID(accepted["dispatch_job_id"])

            first_state = await app.state.workflow_orchestrator.resume_decision(decision_id)
            async with app.state.database.sessions() as db:
                await db.execute(
                    delete(AuditEvent).where(
                        AuditEvent.thread_id == thread_id,
                        AuditEvent.action == "workflow.resume",
                        AuditEvent.outcome == "applied",
                    )
                )
                await db.commit()
            replay_state = await app.state.workflow_orchestrator.resume_decision(decision_id)
            assert first_state["thread_id"] == str(thread_id)
            assert replay_state["thread_id"] == str(thread_id)

            async with app.state.database.sessions() as db:
                assert await app.state.outbox_repository.acknowledge_if_complete(
                    db, outbox_event_id
                )
                await db.commit()
                task_count = int(
                    await db.scalar(
                        select(func.count())
                        .select_from(WorkflowTask)
                        .where(WorkflowTask.proposal_id == proposal_id)
                    )
                    or 0
                )
                task = await db.scalar(
                    select(WorkflowTask).where(WorkflowTask.proposal_id == proposal_id)
                )
                run = await db.get(WorkflowRun, thread_id)
                proposal = await db.get(ActionProposal, proposal_id)
                event = await db.get(OutboxEvent, outbox_event_id)
                applied_audits = int(
                    await db.scalar(
                        select(func.count())
                        .select_from(AuditEvent)
                        .where(
                            AuditEvent.thread_id == thread_id,
                            AuditEvent.action == "workflow.resume",
                            AuditEvent.outcome == "applied",
                        )
                    )
                    or 0
                )
            assert task_count == 1
            assert task is not None and task.title == "Disable vendor access"
            assert run is not None and run.state == WorkflowState.COMPLETED
            assert proposal is not None and proposal.state == ProposalState.EXECUTED
            assert event is not None and event.state == OutboxState.ACKNOWLEDGED
            assert applied_audits == 1
    finally:
        await database.close()
