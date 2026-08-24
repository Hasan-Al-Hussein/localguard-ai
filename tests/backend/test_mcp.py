"""FastMCP inventory, schema, and loopback transport policy tests."""

from __future__ import annotations

import uuid

import httpx
import pytest
from fastmcp import Client
from localguard_api.config import Settings
from localguard_api.database import Database
from localguard_api.providers import DeterministicProvider
from localguard_mcp.schemas import (
    DocumentSectionOutput,
    GetDocumentSectionInput,
    ProposeWorkflowTaskInput,
    SearchDocumentsInput,
)
from localguard_mcp.server import (
    OriginGuardMiddleware,
    create_mcp_http_app,
    create_mcp_server,
)
from pydantic import ValidationError
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

pytestmark = [pytest.mark.unit, pytest.mark.security]


def _settings() -> Settings:
    return Settings(
        app_env="test",
        allow_test_providers=True,
        ai_provider="deterministic",
        embedding_provider="deterministic",
        mcp_allowed_origins=("http://localhost:3000",),
    )


@pytest.mark.asyncio
async def test_mcp_exposes_only_five_bounded_non_privileged_tools() -> None:
    settings = _settings()
    database = Database(settings)
    provider = DeterministicProvider()
    server = create_mcp_server(
        settings=settings,
        database=database,
        embeddings=provider,
    )
    try:
        async with Client(server) as client:
            tools = await client.list_tools()
    finally:
        await database.close()
    assert {item.name for item in tools} == {
        "search_documents",
        "get_document_section",
        "propose_workflow_task",
        "list_pending_approvals",
        "get_audit_event",
    }
    assert all("actor" not in str(item.inputSchema).casefold() for item in tools)
    proposal = next(item for item in tools if item.name == "propose_workflow_task")
    assert proposal.annotations is not None
    assert proposal.annotations.destructiveHint is False
    assert proposal.annotations.openWorldHint is False
    assert proposal.annotations.idempotentHint is True


def test_mcp_input_schemas_reject_model_supplied_identity_and_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SearchDocumentsInput.model_validate(
            {"query": "find policy evidence", "actor_role": "admin"}
        )
    with pytest.raises(ValidationError):
        ProposeWorkflowTaskInput.model_validate(
            {
                "title": "Unsafe",
                "description": "Attempt identity injection",
                "reasoning_summary": "test",
                "cited_chunk_ids": ["a" * 64],
                "approved": True,
            }
        )


@pytest.mark.asyncio
async def test_loopback_origin_guard_rejects_unknown_browser_origin() -> None:
    async def endpoint(scope: Scope, receive: Receive, send: Send) -> None:
        await JSONResponse({"ok": True})(scope, receive, send)

    app = OriginGuardMiddleware(endpoint, allowed_origins=("http://localhost:3000",))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        denied = await client.get("/mcp", headers={"Origin": "https://evil.invalid"})
        allowed = await client.get("/mcp", headers={"Origin": "http://localhost:3000"})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "origin_denied"
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_fastmcp_transport_rejects_host_header_outside_loopback() -> None:
    settings = _settings()
    database = Database(settings)
    server = create_mcp_server(
        settings=settings,
        database=database,
        embeddings=DeterministicProvider(),
    )
    app = create_mcp_http_app(server, settings)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            denied = await client.get("/mcp", headers={"Host": "evil.invalid"})
            loopback = await client.get("/mcp", headers={"Host": "localhost"})
    finally:
        await database.close()
    assert denied.status_code == 421
    assert loopback.status_code != 421


def test_mcp_errors_are_structured_without_internal_details() -> None:
    schema = ProposeWorkflowTaskInput.model_json_schema()
    assert schema["additionalProperties"] is False
    assert "actor_id" not in str(schema).casefold()


def test_document_section_contract_enforces_bounded_exact_ranges() -> None:
    with pytest.raises(ValidationError):
        GetDocumentSectionInput(
            document_id=uuid.uuid4(),
            anchor_key="lines:1-10",
            max_chars=8001,
        )
    output = DocumentSectionOutput(
        document_id=uuid.uuid4(),
        revision_id=uuid.uuid4(),
        anchor_key="lines:1-10",
        anchor_label="Lines 1-10",
        kind="text_lines",
        start_offset=100,
        end_offset=8100,
        total_characters=9000,
        truncated=True,
        text="x" * 8000,
    )
    assert len(output.text) == 8000
    with pytest.raises(ValidationError):
        DocumentSectionOutput.model_validate({**output.model_dump(), "end_offset": 8101})
