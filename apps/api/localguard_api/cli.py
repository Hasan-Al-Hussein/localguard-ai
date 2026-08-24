"""Idempotent local bootstrap commands; generated credentials are printed once."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import delete, select, text, update

from .agent.checkpoints import setup_postgres_checkpoints
from .config import Settings, get_settings
from .database import Database
from .demo import run_demo
from .ingestion import PrivateUploadStore
from .models import (
    ActionProposal,
    ApprovalDecision,
    Citation,
    Document,
    DocumentRevision,
    MCPAccessToken,
    QuestionJob,
    Role,
    SessionToken,
    User,
    WorkflowRun,
    WorkflowTask,
    utc_now,
)
from .security import hash_password, normalize_username, token_digest

cli = typer.Typer(no_args_is_help=True)
_CHECKPOINT_PURGE_CONFIRMATION = "PURGE CHECKPOINT HISTORY"
_ORPHAN_CITATION_PURGE_CONFIRMATION = "PURGE ORPHAN CITATIONS"


async def _upsert_user(
    db: Database, username: str, display_name: str, role: Role, password: str
) -> None:
    normalized = normalize_username(username)
    async with db.sessions() as session:
        user = await session.scalar(select(User).where(User.username == normalized))
        if user is None:
            user = User(
                username=normalized,
                display_name=display_name,
                role=role,
                password_hash=hash_password(password),
            )
            session.add(user)
        else:
            user.display_name = display_name
            user.role = role
            user.password_hash = hash_password(password)
            user.is_active = True
            await session.execute(
                update(SessionToken)
                .where(
                    SessionToken.user_id == user.id,
                    SessionToken.revoked_at.is_(None),
                )
                .values(revoked_at=utc_now())
            )
        await session.commit()


def _mcp_bootstrap_token_value(settings: Settings) -> str:
    if (
        settings.mcp_bootstrap_token is None
        or settings.mcp_bootstrap_token.get_secret_value().startswith("generated-by-bootstrap")
    ):
        raise typer.BadParameter("MCP_BOOTSTRAP_TOKEN must be generated before synchronization")
    return settings.mcp_bootstrap_token.get_secret_value()


async def _sync_mcp_bootstrap_token(database: Database, settings: Settings) -> None:
    raw_token = _mcp_bootstrap_token_value(settings)
    async with database.sessions() as session:
        admin = await session.scalar(select(User).where(User.username == "demo-admin"))
        if admin is None:
            raise typer.BadParameter("demo-admin must be seeded before MCP token synchronization")
        digest = token_digest(raw_token)
        expires_at = utc_now() + timedelta(days=settings.mcp_bootstrap_token_ttl_days)
        await session.execute(
            update(MCPAccessToken)
            .where(
                MCPAccessToken.label == "bootstrap",
                MCPAccessToken.token_hash != digest,
                MCPAccessToken.revoked_at.is_(None),
            )
            .values(revoked_at=utc_now())
        )
        token = await session.scalar(
            select(MCPAccessToken).where(MCPAccessToken.token_hash == digest)
        )
        if token is None:
            session.add(
                MCPAccessToken(
                    token_hash=digest,
                    user_id=admin.id,
                    label="bootstrap",
                    expires_at=expires_at,
                )
            )
        else:
            if token.label != "bootstrap":
                raise typer.BadParameter(
                    "Configured MCP bootstrap token is already assigned to another credential"
                )
            token.user_id = admin.id
            token.expires_at = expires_at
            token.revoked_at = None
        await session.commit()


async def _seed_all(settings: Settings) -> None:
    configured = {
        Role.ADMIN: settings.bootstrap_admin_password,
        Role.REVIEWER: settings.bootstrap_reviewer_password,
        Role.VIEWER: settings.bootstrap_viewer_password,
    }
    if any(
        secret is None or secret.get_secret_value().startswith("generated-by-bootstrap")
        for secret in configured.values()
    ):
        raise typer.BadParameter("Bootstrap passwords must be generated before seeding")
    _mcp_bootstrap_token_value(settings)

    database = Database(settings)
    try:
        for role, secret in configured.items():
            assert secret is not None
            await _upsert_user(
                database,
                f"demo-{role.value}",
                f"Demo {role.value.title()}",
                role,
                secret.get_secret_value(),
            )
        await _sync_mcp_bootstrap_token(database, settings)
    finally:
        await database.close()


async def _purge_checkpoint_history(settings: Settings, *, confirmation: str) -> dict[str, int]:
    if confirmation != _CHECKPOINT_PURGE_CONFIRMATION:
        raise typer.BadParameter(
            f'Type "{_CHECKPOINT_PURGE_CONFIRMATION}" exactly to purge checkpoint history'
        )
    database = Database(settings)
    try:
        async with database.sessions() as session:
            await session.execute(
                text(
                    "LOCK TABLE checkpoint_writes, checkpoint_blobs, checkpoints "
                    "IN ACCESS EXCLUSIVE MODE"
                )
            )
            counts = {
                "checkpoint_writes": int(
                    await session.scalar(text("SELECT count(*) FROM checkpoint_writes")) or 0
                ),
                "checkpoint_blobs": int(
                    await session.scalar(text("SELECT count(*) FROM checkpoint_blobs")) or 0
                ),
                "checkpoints": int(
                    await session.scalar(text("SELECT count(*) FROM checkpoints")) or 0
                ),
            }
            await session.execute(text("DELETE FROM checkpoint_writes"))
            await session.execute(text("DELETE FROM checkpoint_blobs"))
            await session.execute(text("DELETE FROM checkpoints"))
            await session.commit()
            return counts
    finally:
        await database.close()


def _write_new_private_json(output: Path, payload: dict[str, object]) -> Path:
    resolved_output = output.expanduser().resolve()
    if not resolved_output.parent.is_dir():
        raise typer.BadParameter("The export output directory does not exist")
    descriptor = os.open(
        resolved_output,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except BaseException:
        resolved_output.unlink(missing_ok=True)
        raise
    return resolved_output


async def _export_orphan_citations(settings: Settings, *, output: Path) -> tuple[Path, int]:
    database = Database(settings)
    try:
        async with database.sessions() as session:
            citations = list(
                (
                    await session.scalars(
                        select(Citation)
                        .where(Citation.chunk_id.is_(None))
                        .order_by(Citation.answer_id, Citation.ordinal, Citation.id)
                    )
                ).all()
            )
    finally:
        await database.close()
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "exported_at": utc_now().isoformat(),
        "count": len(citations),
        "citations": [
            {
                "id": str(item.id),
                "answer_id": str(item.answer_id),
                "ordinal": item.ordinal,
                "quote": item.quote,
                "document_id": str(item.document_id),
                "revision_id": str(item.revision_id),
                "anchor_key": item.anchor_key,
                "anchor_label": item.anchor_label,
                "start_offset": item.start_offset,
                "end_offset": item.end_offset,
            }
            for item in citations
        ],
    }
    resolved_output = await asyncio.to_thread(_write_new_private_json, output, payload)
    return resolved_output, len(citations)


async def _purge_orphan_citations(settings: Settings, *, confirmation: str) -> int:
    if confirmation != _ORPHAN_CITATION_PURGE_CONFIRMATION:
        raise typer.BadParameter(
            f'Type "{_ORPHAN_CITATION_PURGE_CONFIRMATION}" exactly to purge orphan citations'
        )
    database = Database(settings)
    try:
        async with database.sessions() as session:
            await session.execute(text("LOCK TABLE citations IN ACCESS EXCLUSIVE MODE"))
            count = int(
                await session.scalar(text("SELECT count(*) FROM citations WHERE chunk_id IS NULL"))
                or 0
            )
            await session.execute(text("DELETE FROM citations WHERE chunk_id IS NULL"))
            await session.commit()
            return count
    finally:
        await database.close()


@cli.command("seed")
def seed() -> None:
    """Create/update the three local demo principals from bootstrap environment secrets."""

    settings = get_settings()
    asyncio.run(_seed_all(settings))
    typer.echo("Local demo users seeded without exposing credentials.")


@cli.command("sync-mcp-token")
def sync_mcp_token() -> None:
    """Rotate/refresh only the bootstrap MCP bearer without changing user credentials."""

    async def run() -> None:
        settings = get_settings()
        database = Database(settings)
        try:
            await _sync_mcp_bootstrap_token(database, settings)
        finally:
            await database.close()

    asyncio.run(run())
    typer.echo("Bootstrap MCP token synchronized with a finite expiry.")


async def _reset_demo_data(settings: Settings) -> list[str]:
    database = Database(settings)
    demo_usernames = {"demo-admin", "demo-reviewer", "demo-viewer"}
    storage_keys: list[str] = []
    try:
        async with database.sessions() as session:
            user_ids = list(
                (
                    await session.scalars(select(User.id).where(User.username.in_(demo_usernames)))
                ).all()
            )
            if not user_ids:
                return []
            document_ids = list(
                (
                    await session.scalars(
                        select(Document.id).where(Document.created_by_id.in_(user_ids))
                    )
                ).all()
            )
            if document_ids:
                storage_keys = list(
                    (
                        await session.scalars(
                            select(DocumentRevision.storage_key).where(
                                DocumentRevision.document_id.in_(document_ids)
                            )
                        )
                    ).all()
                )
                await session.execute(
                    update(Document)
                    .where(Document.id.in_(document_ids))
                    .values(current_revision_id=None)
                )
            await session.execute(
                delete(QuestionJob).where(QuestionJob.requested_by_id.in_(user_ids))
            )
            workflow_ids = list(
                (
                    await session.scalars(
                        select(WorkflowRun.id).where(WorkflowRun.requested_by_id.in_(user_ids))
                    )
                ).all()
            )
            if workflow_ids:
                proposal_ids = list(
                    (
                        await session.scalars(
                            select(ActionProposal.id).where(
                                ActionProposal.workflow_run_id.in_(workflow_ids)
                            )
                        )
                    ).all()
                )
                if proposal_ids:
                    await session.execute(
                        delete(WorkflowTask).where(WorkflowTask.proposal_id.in_(proposal_ids))
                    )
                    await session.execute(
                        delete(ApprovalDecision).where(
                            ApprovalDecision.proposal_id.in_(proposal_ids)
                        )
                    )
                await session.execute(delete(WorkflowRun).where(WorkflowRun.id.in_(workflow_ids)))
            if document_ids:
                await session.execute(delete(Document).where(Document.id.in_(document_ids)))
            await session.commit()
    finally:
        await database.close()
    return storage_keys


@cli.command("demo")
def demo(
    reset: Annotated[
        bool, typer.Option(help="Remove only data owned by the three demo users before launch.")
    ] = False,
) -> None:
    """Run the real local-provider demo and write auditable verification evidence."""

    settings = get_settings()
    if settings.ai_provider != "ollama" or settings.embedding_provider != "ollama":
        raise typer.BadParameter("The demo command refuses deterministic test providers")
    asyncio.run(_seed_all(settings))
    if reset:
        storage_keys = asyncio.run(_reset_demo_data(settings))
        store = PrivateUploadStore(settings.upload_root)
        for storage_key in storage_keys:
            store.delete(storage_key)
        typer.echo("Demo-owned documents and questions were reset.")
    repository_root = Path.cwd().resolve()
    artifact_path = repository_root / "artifacts" / "verification" / "demo.json"
    artifact = asyncio.run(
        run_demo(
            settings,
            repository_root=repository_root,
            artifact_path=artifact_path,
        )
    )
    typer.echo(
        "LocalGuard demo verified ingestion, cited Q&A, approval gating, and exactly-once "
        f"task creation in {artifact.total_ms:.1f} ms."
    )
    typer.echo(f"Verification artifact: {artifact_path}")


@cli.command("create-user")
def create_user(
    username: str,
    role: Annotated[Role, typer.Option(case_sensitive=False)] = Role.VIEWER,
    display_name: Annotated[str, typer.Option()] = "LocalGuard User",
) -> None:
    """Create/update one user with a generated password displayed exactly once."""

    password = secrets.token_urlsafe(24)

    async def run() -> None:
        database = Database(get_settings())
        try:
            await _upsert_user(database, username, display_name, role, password)
        finally:
            await database.close()

    asyncio.run(run())
    typer.echo(f"Generated password (shown once): {password}")


@cli.command("setup-checkpoints")
def setup_checkpoints() -> None:
    """Create/update LangGraph checkpoint tables once after database migrations."""

    asyncio.run(setup_postgres_checkpoints(get_settings()))
    typer.echo("LangGraph PostgreSQL checkpoint schema is ready.")


@cli.command("purge-checkpoints")
def purge_checkpoints(
    confirmation: Annotated[
        str,
        typer.Option(
            "--confirm",
            help=f'Type "{_CHECKPOINT_PURGE_CONFIRMATION}" exactly to delete user history.',
        ),
    ] = "",
) -> None:
    """Delete LangGraph user-thread history while preserving its schema and migrations."""

    counts = asyncio.run(_purge_checkpoint_history(get_settings(), confirmation=confirmation))
    typer.echo(
        "Checkpoint history purged: "
        f"writes={counts['checkpoint_writes']}, "
        f"blobs={counts['checkpoint_blobs']}, "
        f"checkpoints={counts['checkpoints']}. "
        "Checkpoint schema and migration metadata were preserved."
    )


@cli.command("export-orphan-citations")
def export_orphan_citations(
    output: Annotated[Path, typer.Option("--output", help="New JSON export file path.")],
) -> None:
    """Export immutable citation snapshots whose source chunks were deleted."""

    resolved_output, count = asyncio.run(_export_orphan_citations(get_settings(), output=output))
    typer.echo(f"Exported {count} orphan citation snapshot(s) to {resolved_output}.")


@cli.command("purge-orphan-citations")
def purge_orphan_citations(
    confirmation: Annotated[
        str,
        typer.Option(
            "--confirm",
            help=f'Type "{_ORPHAN_CITATION_PURGE_CONFIRMATION}" exactly to delete snapshots.',
        ),
    ] = "",
) -> None:
    """Explicitly delete orphan citation snapshots before a Phase-1 downgrade."""

    count = asyncio.run(_purge_orphan_citations(get_settings(), confirmation=confirmation))
    typer.echo(f"Purged {count} orphan citation snapshot(s).")


if __name__ == "__main__":
    cli()
