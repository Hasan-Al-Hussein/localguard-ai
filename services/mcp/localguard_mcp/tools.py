"""The five allowlisted MCP tools; none can execute a privileged action."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar

from fastmcp import Context, FastMCP
from fastmcp.dependencies import CurrentAccessToken, CurrentContext, Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken
from localguard_api.agent.contracts import TaskProposalDraft
from localguard_api.agent.persistence import (
    MCP_DIRECT_WORKFLOW_INTENT,
    WorkflowRepository,
    canonical_hash,
    compute_evidence_snapshot_hash,
    expire_pending_proposals,
)
from localguard_api.config import Settings
from localguard_api.database import Database
from localguard_api.models import ActionProposal, AuditEvent, ProposalState, Role, User, utc_now
from localguard_api.repositories import AuditRepository, audit_repository
from localguard_api.retrieval import EvidenceResolver, HybridRetriever, evidence_resolver
from mcp.types import ToolAnnotations
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import (
    AuditEventOutput,
    DocumentSectionOutput,
    GetAuditEventInput,
    GetDocumentSectionInput,
    ListPendingApprovalsInput,
    PendingApproval,
    PendingApprovalsOutput,
    ProposalOutput,
    ProposeWorkflowTaskInput,
    SearchDocumentsInput,
    SearchDocumentsOutput,
    SearchHit,
    ToolEnvelope,
    ToolErrorBody,
    TrustedPrincipal,
)

ResponseT = TypeVar("ResponseT")
RequestT = TypeVar("RequestT")
_ACCESS_TOKEN = CurrentAccessToken()
_CONTEXT = CurrentContext()


def register_tools(
    mcp: FastMCP,
    *,
    settings: Settings,
    database: Database,
    retriever: HybridRetriever,
    workflow_repository: WorkflowRepository,
    resolver: EvidenceResolver = evidence_resolver,
    audits: AuditRepository = audit_repository,
) -> None:
    async def trusted_principal(
        token: AccessToken = _ACCESS_TOKEN,
    ) -> TrustedPrincipal:
        try:
            return TrustedPrincipal(
                user_id=uuid.UUID(str(token.claims["user_id"])),
                username=str(token.claims["username"]),
                role=Role(str(token.claims["role"])),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ToolError("authentication_context_invalid") from exc

    principal_dependency = Depends(trusted_principal)

    def unexpected_failure_boundary(
        tool: str,
    ) -> Callable[
        [Callable[[RequestT, TrustedPrincipal, Context], Awaitable[ToolEnvelope[ResponseT]]]],
        Callable[[RequestT, TrustedPrincipal, Context], Awaitable[ToolEnvelope[ResponseT]]],
    ]:
        def decorate(
            operation: Callable[
                [RequestT, TrustedPrincipal, Context], Awaitable[ToolEnvelope[ResponseT]]
            ],
        ) -> Callable[[RequestT, TrustedPrincipal, Context], Awaitable[ToolEnvelope[ResponseT]]]:
            @wraps(operation)
            async def guarded(
                request: RequestT,
                principal: TrustedPrincipal = principal_dependency,
                ctx: Context = _CONTEXT,
            ) -> ToolEnvelope[ResponseT]:
                correlation_id = _correlation_id(ctx)
                try:
                    return await operation(request, principal, ctx)
                except ToolError:
                    raise
                except Exception as exc:
                    await _audit_unexpected(database, audits, principal, tool, correlation_id)
                    raise ToolError(f"{tool}_failed") from exc

            return guarded

        return decorate

    @mcp.tool(
        name="search_documents",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        timeout=190.0,
    )
    @unexpected_failure_boundary("search_documents")
    async def search_documents(
        request: SearchDocumentsInput,
        principal: TrustedPrincipal = principal_dependency,
        ctx: Context = _CONTEXT,
    ) -> ToolEnvelope[SearchDocumentsOutput]:
        correlation_id = _correlation_id(ctx)
        try:
            async with database.sessions() as db:
                actor = await _load_actor(db, principal)
                result = await retriever.search(db, request.query, request.document_ids)
                hits = [
                    SearchHit(
                        chunk_id=item.chunk.stable_id,
                        document_id=item.chunk.revision.document_id,
                        document_title=item.chunk.revision.document.title,
                        anchor_key=item.chunk.anchor.stable_key,
                        anchor_label=item.chunk.anchor.label,
                        excerpt=item.chunk.content[:1000],
                        score=item.score,
                        vector_similarity=item.vector_similarity,
                        text_score=item.text_score,
                    )
                    for item in result.chunks[: request.limit]
                ]
                await _audit_tool(
                    db,
                    audits,
                    actor=actor,
                    tool="search_documents",
                    outcome="succeeded",
                    correlation_id=correlation_id,
                    detail={"hit_count": len(hits), "document_count": len(request.document_ids)},
                )
                await db.commit()
            return _success(SearchDocumentsOutput(sufficient=result.sufficient, hits=hits))
        except ToolError:
            raise
        except Exception as exc:
            await _audit_unexpected(database, audits, principal, "search_documents", correlation_id)
            raise ToolError("search_documents_failed") from exc

    @mcp.tool(
        name="get_document_section",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        timeout=10.0,
    )
    @unexpected_failure_boundary("get_document_section")
    async def get_document_section(
        request: GetDocumentSectionInput,
        principal: TrustedPrincipal = principal_dependency,
        ctx: Context = _CONTEXT,
    ) -> ToolEnvelope[DocumentSectionOutput]:
        correlation_id = _correlation_id(ctx)
        async with database.sessions() as db:
            actor = await _load_actor(db, principal)
            anchor = await resolver.get_section(db, request.document_id, request.anchor_key)
            if anchor is None:
                await _audit_tool(
                    db,
                    audits,
                    actor=actor,
                    tool="get_document_section",
                    outcome="not_found",
                    correlation_id=correlation_id,
                )
                await db.commit()
                return _failure("not_found", "Document section was not found")
            if request.offset >= len(anchor.text):
                await _audit_tool(
                    db,
                    audits,
                    actor=actor,
                    tool="get_document_section",
                    outcome="rejected",
                    correlation_id=correlation_id,
                    detail={"reason": "offset_out_of_range"},
                )
                await db.commit()
                return _failure("invalid_range", "Section offset is outside the anchor")
            end_offset = min(len(anchor.text), request.offset + request.max_chars)
            section_text = anchor.text[request.offset : end_offset]
            await _audit_tool(
                db,
                audits,
                actor=actor,
                tool="get_document_section",
                outcome="succeeded",
                correlation_id=correlation_id,
                detail={
                    "document_id": str(request.document_id),
                    "anchor_key": anchor.stable_key,
                    "start_offset": request.offset,
                    "end_offset": end_offset,
                },
            )
            await db.commit()
            return _success(
                DocumentSectionOutput(
                    document_id=request.document_id,
                    revision_id=anchor.revision_id,
                    anchor_key=anchor.stable_key,
                    anchor_label=anchor.label,
                    kind=anchor.kind,
                    start_offset=request.offset,
                    end_offset=end_offset,
                    total_characters=len(anchor.text),
                    truncated=end_offset < len(anchor.text),
                    text=section_text,
                )
            )

    @mcp.tool(
        name="propose_workflow_task",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        timeout=15.0,
    )
    @unexpected_failure_boundary("propose_workflow_task")
    async def propose_workflow_task(
        request: ProposeWorkflowTaskInput,
        principal: TrustedPrincipal = principal_dependency,
        ctx: Context = _CONTEXT,
    ) -> ToolEnvelope[ProposalOutput]:
        correlation_id = _correlation_id(ctx)
        async with database.sessions() as db:
            actor = await _load_actor(db, principal)
            resolved = await resolver.resolve_chunks(db, request.cited_chunk_ids)
            if set(resolved) != set(request.cited_chunk_ids):
                await _audit_tool(
                    db,
                    audits,
                    actor=actor,
                    tool="propose_workflow_task",
                    outcome="rejected",
                    correlation_id=correlation_id,
                    detail={"reason": "citation_resolution_failed"},
                )
                await db.commit()
                return _failure("invalid_citations", "One or more citation IDs did not resolve")
            document_ids = sorted(
                {item.revision.document_id for item in resolved.values()}, key=str
            )
            draft = TaskProposalDraft(
                title=request.title,
                description=request.description,
                assignee=request.assignee,
                priority=request.priority,
                due_at=request.due_at,
                reasoning_summary=request.reasoning_summary,
                cited_chunk_ids=request.cited_chunk_ids,
            )
            evidence_snapshot_hash = compute_evidence_snapshot_hash(
                (key, value.content) for key, value in resolved.items()
            )
            payload_hash = canonical_hash(draft.model_dump(mode="json"))
            lock_material = hashlib.sha256(
                f"{actor.id}:{payload_hash}:{evidence_snapshot_hash}".encode()
            ).digest()
            lock_key = int.from_bytes(lock_material[:8], "big", signed=True)
            await db.execute(select(func.pg_advisory_xact_lock(lock_key)))
            proposal = await db.scalar(
                select(ActionProposal)
                .where(
                    ActionProposal.created_by_id == actor.id,
                    ActionProposal.payload_hash == payload_hash,
                    ActionProposal.evidence_snapshot_hash == evidence_snapshot_hash,
                    ActionProposal.state == ProposalState.PENDING,
                    ActionProposal.expires_at > utc_now(),
                )
                .order_by(ActionProposal.created_at.desc())
                .limit(1)
            )
            outcome = "duplicate"
            if proposal is None:
                run = await workflow_repository.create_run(
                    db,
                    actor=actor,
                    question=f"MCP proposal: {request.title}",
                    document_ids=document_ids,
                    correlation_id=correlation_id,
                )
                run.intent = MCP_DIRECT_WORKFLOW_INTENT
                proposal = await workflow_repository.upsert_proposal(
                    db,
                    run_id=run.id,
                    actor_id=actor.id,
                    draft=draft,
                    evidence_snapshot_hash=evidence_snapshot_hash,
                )
                outcome = "pending"
            await _audit_tool(
                db,
                audits,
                actor=actor,
                tool="propose_workflow_task",
                outcome=outcome,
                correlation_id=correlation_id,
                thread_id=proposal.workflow_run_id,
                resource_id=proposal.id,
                detail={"proposal_version": proposal.version},
            )
            await db.commit()
            return _success(
                ProposalOutput(
                    proposal_id=proposal.id,
                    thread_id=proposal.workflow_run_id,
                    version=proposal.version,
                    status=proposal.state,
                    payload_hash=proposal.payload_hash,
                    evidence_snapshot_hash=proposal.evidence_snapshot_hash,
                    approval_required=True,
                )
            )

    @mcp.tool(
        name="list_pending_approvals",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        timeout=10.0,
    )
    @unexpected_failure_boundary("list_pending_approvals")
    async def list_pending_approvals(
        request: ListPendingApprovalsInput,
        principal: TrustedPrincipal = principal_dependency,
        ctx: Context = _CONTEXT,
    ) -> ToolEnvelope[PendingApprovalsOutput]:
        correlation_id = _correlation_id(ctx)
        async with database.sessions() as db:
            actor = await _load_actor(db, principal)
            if actor.role not in {Role.REVIEWER, Role.ADMIN}:
                await _audit_tool(
                    db,
                    audits,
                    actor=actor,
                    tool="list_pending_approvals",
                    outcome="denied",
                    correlation_id=correlation_id,
                )
                await db.commit()
                return _failure("permission_denied", "Reviewer permission is required")
            await expire_pending_proposals(
                db,
                correlation_id=correlation_id,
                actor_id=actor.id,
                audits=audits,
            )
            proposals, _ = await workflow_repository.list_proposals(
                db,
                states=[ProposalState.PENDING],
                offset=0,
                limit=request.limit,
            )
            items = [
                PendingApproval(
                    proposal_id=item.id,
                    thread_id=item.workflow_run_id,
                    version=item.version,
                    title=item.title,
                    priority=item.priority,
                    due_at=item.due_at,
                    expires_at=item.expires_at,
                    payload_hash=item.payload_hash,
                )
                for item in proposals
            ]
            await _audit_tool(
                db,
                audits,
                actor=actor,
                tool="list_pending_approvals",
                outcome="succeeded",
                correlation_id=correlation_id,
                detail={"result_count": len(items)},
            )
            await db.commit()
            return _success(PendingApprovalsOutput(items=items))

    @mcp.tool(
        name="get_audit_event",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        timeout=10.0,
    )
    @unexpected_failure_boundary("get_audit_event")
    async def get_audit_event(
        request: GetAuditEventInput,
        principal: TrustedPrincipal = principal_dependency,
        ctx: Context = _CONTEXT,
    ) -> ToolEnvelope[AuditEventOutput]:
        correlation_id = _correlation_id(ctx)
        async with database.sessions() as db:
            actor = await _load_actor(db, principal)
            if actor.role not in {Role.REVIEWER, Role.ADMIN}:
                await _audit_tool(
                    db,
                    audits,
                    actor=actor,
                    tool="get_audit_event",
                    outcome="denied",
                    correlation_id=correlation_id,
                )
                await db.commit()
                return _failure("permission_denied", "Reviewer permission is required")
            event = await db.get(AuditEvent, request.event_id)
            if event is None:
                await _audit_tool(
                    db,
                    audits,
                    actor=actor,
                    tool="get_audit_event",
                    outcome="not_found",
                    correlation_id=correlation_id,
                )
                await db.commit()
                return _failure("not_found", "Audit event was not found")
            await _audit_tool(
                db,
                audits,
                actor=actor,
                tool="get_audit_event",
                outcome="succeeded",
                correlation_id=correlation_id,
                resource_id=event.id,
            )
            await db.commit()
            return _success(
                AuditEventOutput(
                    event_id=event.id,
                    occurred_at=event.occurred_at,
                    actor_id=event.actor_id,
                    action=event.action,
                    resource_type=event.resource_type,
                    resource_id=event.resource_id,
                    outcome=event.outcome,
                    correlation_id=event.correlation_id,
                    causation_id=event.causation_id,
                    thread_id=event.thread_id,
                    detail=_redact_detail(event.detail),
                )
            )


async def _load_actor(db: AsyncSession, principal: TrustedPrincipal) -> User:
    actor = await db.get(User, principal.user_id)
    if not isinstance(actor, User) or not actor.is_active or actor.role != principal.role:
        raise ToolError("authentication_context_stale")
    return actor


async def _audit_tool(
    db: AsyncSession,
    audits: AuditRepository,
    *,
    actor: User,
    tool: str,
    outcome: str,
    correlation_id: str,
    resource_id: uuid.UUID | None = None,
    thread_id: uuid.UUID | None = None,
    detail: dict[str, object] | None = None,
) -> None:
    await audits.add(
        db,
        actor_id=actor.id,
        action=f"mcp.{tool}",
        resource_type="mcp_tool_call",
        resource_id=resource_id,
        outcome=outcome,
        correlation_id=correlation_id,
        thread_id=thread_id,
        detail={"tool": tool, **(detail or {})},
    )


async def _audit_unexpected(
    database: Database,
    audits: AuditRepository,
    principal: TrustedPrincipal,
    tool: str,
    correlation_id: str,
) -> None:
    try:
        async with database.sessions() as db:
            actor = await db.get(User, principal.user_id)
            if actor is not None:
                await _audit_tool(
                    db,
                    audits,
                    actor=actor,
                    tool=tool,
                    outcome="failed",
                    correlation_id=correlation_id,
                )
                await db.commit()
    except Exception:
        # The primary tool error remains masked even if the audit store is unavailable.
        return


def _success(  # noqa: UP047 - Python 3.11 compatibility
    value: ResponseT,
) -> ToolEnvelope[ResponseT]:
    return ToolEnvelope[ResponseT](ok=True, data=value)


def _failure(code: str, message: str) -> ToolEnvelope[Any]:
    return ToolEnvelope[Any](ok=False, error=ToolErrorBody(code=code, message=message))


def _correlation_id(ctx: Context | None) -> str:
    if ctx is None:
        return f"mcp-{uuid.uuid4().hex}"
    value = str(ctx.request_id)
    return value[:64] if value else f"mcp-{uuid.uuid4().hex}"


def _redact_detail(value: dict[str, object]) -> dict[str, object]:
    blocked = ("password", "secret", "token", "content")
    return {
        key: "[REDACTED]" if any(term in key.casefold() for term in blocked) else item
        for key, item in value.items()
    }
