"""Real-PostgreSQL verification of the automated demo contract."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest
from localguard_api.agent.api import get_task
from localguard_api.config import Settings
from localguard_api.database import Database
from localguard_api.demo import DemoArtifact, run_demo
from localguard_api.errors import AuthorizationError
from localguard_api.models import AuditEvent, Document, Role, User, WorkflowTask
from localguard_api.providers import DeterministicProvider
from localguard_api.security import hash_password
from sqlalchemy import func, select

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_INTEGRATION") != "1",
        reason="set RUN_DB_INTEGRATION=1 inside the local Compose network",
    ),
]

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_demo_runner_proves_citations_approval_and_exactly_once_task(
    tmp_path: Path,
) -> None:
    settings = Settings(
        app_env="test",
        allow_test_providers=True,
        ai_provider="deterministic",
        embedding_provider="deterministic",
        upload_root=tmp_path / "uploads",
        retrieval_min_score=0,
        retrieval_min_vector_similarity=-1,
        retrieval_min_text_score=0,
        allowed_hosts=("testserver",),
    )
    database = Database(settings)
    suffix = uuid.uuid4().hex
    viewer_username = f"demo-test-viewer-{suffix}"
    reviewer_username = f"demo-test-reviewer-{suffix}"
    viewer = User(
        username=viewer_username,
        display_name="Demo Test Viewer",
        password_hash=hash_password("demo integration viewer password"),
        role=Role.VIEWER,
    )
    reviewer = User(
        username=reviewer_username,
        display_name="Demo Test Reviewer",
        password_hash=hash_password("demo integration reviewer password"),
        role=Role.REVIEWER,
    )
    outsider = User(
        username=f"demo-test-outsider-{suffix}",
        display_name="Demo Test Outsider",
        password_hash=hash_password("demo integration outsider password"),
        role=Role.VIEWER,
    )
    async with database.sessions() as db:
        db.add_all([viewer, reviewer, outsider])
        await db.commit()
    artifact_path = tmp_path / "artifacts" / "demo.json"
    try:
        result = await run_demo(
            settings,
            repository_root=ROOT,
            artifact_path=artifact_path,
            viewer_username=viewer_username,
            reviewer_username=reviewer_username,
        )

        persisted = DemoArtifact.model_validate(json.loads(artifact_path.read_text("utf-8")))
        assert persisted == result
        assert result.chat_model == DeterministicProvider.model_name
        assert result.embedding_model == DeterministicProvider.embedding_model_name
        assert result.embedding_model != result.chat_model
        assert result.status == "verified"
        assert result.proof_scope == "in_process_domain"
        assert result.question.citations
        assert result.approval_workflow.cited_chunk_ids
        assert result.approval_workflow.tasks_before_approval == 0
        assert result.approval_workflow.tasks_after_approval == 1
        assert result.approval_workflow.tasks_after_replay == 1
        assert result.audit.actions == [
            "document.upload",
            "ingestion.process",
            "ingestion.process",
            "question.request",
            "question.process",
            "question.process",
            "workflow.request",
            "workflow.analysis",
            "proposal.create",
            "proposal.approve",
            "workflow.resume",
            "workflow_task.create",
            "workflow.resume",
        ]
        async with database.sessions() as db:
            uploaded = await db.get(Document, result.document.document_id)
            assert uploaded is not None and uploaded.created_by_id == reviewer.id
            assert (
                int(
                    await db.scalar(
                        select(func.count())
                        .select_from(WorkflowTask)
                        .where(WorkflowTask.id == result.approval_workflow.task_id)
                    )
                    or 0
                )
                == 1
            )
            audit_count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(AuditEvent.id.in_(result.audit.event_ids))
                )
                or 0
            )
            assert audit_count == len(result.audit.event_ids)
            assert (
                await get_task(result.approval_workflow.task_id, viewer, db)
            ).id == result.approval_workflow.task_id
            assert (
                await get_task(result.approval_workflow.task_id, reviewer, db)
            ).id == result.approval_workflow.task_id
            with pytest.raises(AuthorizationError):
                await get_task(result.approval_workflow.task_id, outsider, db)
    finally:
        await database.close()
