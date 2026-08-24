from __future__ import annotations

import httpx
import pytest
from localguard_api.config import Settings
from localguard_api.main import create_app

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_live_health_has_correlation_and_security_headers() -> None:
    settings = Settings(
        app_env="test",
        allow_test_providers=True,
        ai_provider="deterministic",
        embedding_provider="deterministic",
        allowed_hosts=("testserver",),
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/health/live", headers={"X-Correlation-ID": "test-correlation-123"}
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {}}
    assert response.headers["x-correlation-id"] == "test-correlation-123"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


@pytest.mark.asyncio
async def test_untrusted_host_is_rejected() -> None:
    settings = Settings(allowed_hosts=("localhost",))
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://attacker.invalid") as client:
        response = await client.get("/health/live")
    assert response.status_code == 400


def test_phase_one_route_contract_is_present() -> None:
    app = create_app(
        Settings(
            app_env="test",
            allow_test_providers=True,
            ai_provider="deterministic",
            embedding_provider="deterministic",
        )
    )
    paths = app.openapi()["paths"]
    assert "post" in paths["/auth/login"]
    assert "get" in paths["/auth/me"]
    assert "get" in paths["/auth/csrf"]
    assert "post" in paths["/auth/logout"]
    assert "get" in paths["/overview"]
    assert {"get", "post"} <= paths["/documents"].keys()
    assert "post" in paths["/questions"]


def test_phase_two_and_immutable_evidence_route_contracts_are_present() -> None:
    app = create_app(
        Settings(
            app_env="test",
            allow_test_providers=True,
            ai_provider="deterministic",
            embedding_provider="deterministic",
        )
    )
    paths = app.openapi()["paths"]
    assert {"post"} <= paths["/workflow-runs"].keys()
    assert {"get"} <= paths["/findings"].keys()
    assert {"get"} <= paths["/approvals"].keys()
    assert {"get"} <= paths["/tasks/{task_id}"].keys()
    assert {"patch"} <= paths["/tasks/{task_id}"].keys()
    assert {"get"} <= paths["/audit-events/{event_id}"].keys()
    assert {"get"} <= paths["/evaluations"].keys()
    assert {"get"} <= paths["/evaluations/latest"].keys()
    assert {"get"} <= paths["/evaluations/{run_id}"].keys()
    revision_section = "/documents/{document_id}/revisions/{revision_id}/anchors/{anchor_key}"
    assert {"get"} <= paths[revision_section].keys()
