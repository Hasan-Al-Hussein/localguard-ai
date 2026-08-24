"""Phase 1 HTTP routes with explicit authentication and response models."""

from __future__ import annotations

import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import AuthService
from .dependencies import (
    get_auth_service,
    get_current_session,
    get_current_user,
    get_db,
    require_csrf,
    require_roles,
)
from .errors import AuthenticationError, NotFoundError, ServiceUnavailableError
from .evaluation_routes import load_latest_history_entry
from .ingestion import validate_upload
from .models import Answer, Citation, JobState, QuestionJob, Role, SessionToken, User
from .repositories import audit_repository, document_repository, question_repository
from .schemas import (
    AnchorPublic,
    AnswerPublic,
    CitationPublic,
    CSRFResponse,
    DocumentDetail,
    DocumentList,
    DocumentSummary,
    EvaluationOverview,
    HealthResponse,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    OverviewPublic,
    QuestionJobPublic,
    QuestionRequest,
    RevisionPublic,
    RevisionSectionPublic,
    UploadAccepted,
    UserPublic,
)
from .services import overview

public_router = APIRouter()
auth_router = APIRouter(prefix="/auth", tags=["authentication"])
protected_router = APIRouter(dependencies=[Depends(get_current_user)])

DBSession = Annotated[AsyncSession, Depends(get_db)]
AuthDependency = Annotated[AuthService, Depends(get_auth_service)]
CurrentSession = Annotated[SessionToken, Depends(get_current_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CSRFUser = Annotated[User, Depends(require_csrf)]
ReviewerUser = Annotated[User, Depends(require_roles(Role.REVIEWER, Role.ADMIN, csrf=True))]
AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN, csrf=True))]


def _set_session_cookies(
    response: Response,
    auth: AuthService,
    *,
    session_token: str,
    csrf_token: str,
) -> None:
    max_age = auth.settings.session_ttl_minutes * 60
    response.set_cookie(
        auth.settings.session_cookie_name,
        session_token,
        max_age=max_age,
        httponly=True,
        secure=auth.settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        auth.settings.csrf_cookie_name,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=auth.settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


@public_router.get("/health/live", response_model=HealthResponse, tags=["health"])
async def health_live() -> HealthResponse:
    return HealthResponse(status="ok")


@public_router.get("/health/ready", response_model=HealthResponse, tags=["health"])
async def health_ready(request: Request) -> HealthResponse:
    checks: dict[str, str] = {}
    try:
        await request.app.state.database.ping()
        checks["database"] = "ok"
        if not await request.app.state.redis.ping():
            raise RuntimeError("Redis ping failed")
        checks["redis"] = "ok"
        ollama = request.app.state.ollama_provider
        if ollama is not None:
            await ollama.health()
            checks["ollama"] = "ok"
    except Exception as exc:
        raise ServiceUnavailableError(
            "not_ready", "A required local service is unavailable"
        ) from exc
    return HealthResponse(status="ok", checks=checks)


@auth_router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: DBSession,
    auth: AuthDependency,
) -> LoginResponse:
    issued = await auth.login(
        db,
        username=body.username,
        password=body.password,
        user_agent=request.headers.get("user-agent"),
    )
    await audit_repository.add(
        db,
        actor_id=issued.user.id,
        action="auth.login",
        resource_type="session",
        resource_id=None,
        outcome="succeeded",
        correlation_id=request.state.correlation_id,
    )
    _set_session_cookies(
        response,
        auth,
        session_token=issued.session_token,
        csrf_token=issued.csrf_token,
    )
    return LoginResponse(user=UserPublic.model_validate(issued.user), csrf_token=issued.csrf_token)


@auth_router.get("/me", response_model=UserPublic)
async def me(user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(user)


@auth_router.get("/csrf", response_model=CSRFResponse)
async def csrf(
    request: Request,
    response: Response,
    session: CurrentSession,
    auth: AuthDependency,
) -> CSRFResponse:
    existing = request.cookies.get(auth.settings.csrf_cookie_name)
    try:
        auth.verify_csrf(session, header_token=existing, cookie_token=existing)
        token = existing
    except AuthenticationError:
        token = auth.rotate_csrf(session)
        response.set_cookie(
            auth.settings.csrf_cookie_name,
            token,
            max_age=auth.settings.session_ttl_minutes * 60,
            httponly=False,
            secure=auth.settings.session_cookie_secure,
            samesite="lax",
            path="/",
        )
    return CSRFResponse(csrf_token=token)


@auth_router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    user: CSRFUser,
    db: DBSession,
    auth: AuthDependency,
) -> MessageResponse:
    await auth.logout(db, request.cookies.get(auth.settings.session_cookie_name))
    await audit_repository.add(
        db,
        actor_id=user.id,
        action="auth.logout",
        resource_type="session",
        resource_id=None,
        outcome="succeeded",
        correlation_id=request.state.correlation_id,
    )
    response.delete_cookie(auth.settings.session_cookie_name, path="/")
    response.delete_cookie(auth.settings.csrf_cookie_name, path="/")
    return MessageResponse(message="Signed out")


@protected_router.get("/overview", response_model=OverviewPublic, tags=["overview"])
async def get_overview(db: DBSession) -> OverviewPublic:
    payload = await overview(db)
    latest = load_latest_history_entry()
    if latest is not None:
        payload["evaluation_summary"] = EvaluationOverview(
            run_id=latest.run_id,
            schema_version=latest.schema_version,
            runtime_provider=latest.runtime_provider,
            completed_case_count=latest.completed_case_count,
            case_count=latest.case_count,
            safety_passed=latest.safety_passed,
            quality_passed=latest.quality_passed,
            run_passed=latest.run_passed,
            integrity_status=latest.integrity_status,
            integrity_note=latest.integrity_note,
            comparability_status=latest.comparability_status,
            comparability_note=latest.comparability_note,
        )
    return OverviewPublic.model_validate(payload)


@protected_router.get("/documents", response_model=DocumentList, tags=["documents"])
async def list_documents(
    db: DBSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> DocumentList:
    items, total = await document_repository.list_documents(db, offset=offset, limit=limit)
    return DocumentList(
        items=[DocumentSummary.model_validate(item) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@protected_router.post(
    "/documents",
    response_model=UploadAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["documents"],
)
async def upload_document(
    request: Request,
    file: UploadFile,
    actor: ReviewerUser,
    db: DBSession,
) -> UploadAccepted:
    validated = await validate_upload(file, request.app.state.settings)
    accepted = await request.app.state.document_service.accept(db, validated, actor)
    task_id = (
        await request.app.state.outbox_dispatcher.dispatch_one(accepted.dispatch_event_id)
        if accepted.dispatch_event_id is not None
        else None
    )
    return UploadAccepted(
        document=DocumentSummary.model_validate(accepted.document),
        revision_id=accepted.revision.id,
        ingestion_job_id=task_id,
        duplicate=accepted.duplicate,
    )


@protected_router.get("/documents/{document_id}", response_model=DocumentDetail, tags=["documents"])
async def get_document(
    document_id: uuid.UUID,
    request: Request,
    db: DBSession,
) -> DocumentDetail:
    document, revision, anchors = await request.app.state.document_service.detail(db, document_id)
    return DocumentDetail(
        **DocumentSummary.model_validate(document).model_dump(),
        current_revision=RevisionPublic.model_validate(revision) if revision else None,
        anchors=[AnchorPublic.model_validate(anchor) for anchor in anchors],
    )


@protected_router.get(
    "/documents/{document_id}/pages/{page}", response_model=AnchorPublic, tags=["documents"]
)
async def get_document_page(
    document_id: uuid.UUID,
    page: int,
    request: Request,
    db: DBSession,
) -> AnchorPublic:
    if page < 1 or page > request.app.state.settings.max_pdf_pages:
        raise NotFoundError("PDF page")
    anchor = await request.app.state.document_service.page(db, document_id, page)
    return AnchorPublic.model_validate(anchor)


@protected_router.get(
    "/documents/{document_id}/revisions/{revision_id}/anchors/{anchor_key}",
    response_model=RevisionSectionPublic,
    tags=["documents"],
)
async def get_revision_section(
    document_id: uuid.UUID,
    revision_id: uuid.UUID,
    anchor_key: str,
    request: Request,
    db: DBSession,
    start_offset: Annotated[int, Query(ge=0)] = 0,
    end_offset: Annotated[int, Query(ge=1, le=1_000_000)] = 1,
) -> RevisionSectionPublic:
    anchor, text = await request.app.state.document_service.revision_section(
        db,
        document_id=document_id,
        revision_id=revision_id,
        anchor_key=anchor_key,
        start_offset=start_offset,
        end_offset=end_offset,
    )
    return RevisionSectionPublic(
        document_id=document_id,
        revision_id=revision_id,
        anchor_key=anchor.stable_key,
        anchor_label=anchor.label,
        kind=anchor.kind,
        anchor_start_offset=anchor.start_offset,
        anchor_end_offset=anchor.end_offset,
        requested_start_offset=start_offset,
        requested_end_offset=end_offset,
        text=text,
    )


@protected_router.post(
    "/documents/{document_id}/reprocess", response_model=UploadAccepted, tags=["documents"]
)
async def reprocess_document(
    document_id: uuid.UUID,
    request: Request,
    actor: ReviewerUser,
    db: DBSession,
) -> UploadAccepted:
    revision, event_id = await request.app.state.document_service.queue_reprocess(
        db, document_id, actor
    )
    await db.commit()
    task_id = await request.app.state.outbox_dispatcher.dispatch_one(event_id)
    document = await document_repository.get(db, document_id)
    if document is None:
        raise NotFoundError("Document")
    return UploadAccepted(
        document=DocumentSummary.model_validate(document),
        revision_id=revision.id,
        ingestion_job_id=task_id,
    )


@protected_router.delete(
    "/documents/{document_id}", response_model=MessageResponse, tags=["documents"]
)
async def delete_document(
    document_id: uuid.UUID,
    request: Request,
    actor: AdminUser,
    db: DBSession,
) -> MessageResponse:
    await request.app.state.document_service.soft_delete(db, document_id, actor)
    await db.commit()
    await request.app.state.cleanup_processor.process_one()
    return MessageResponse(message="Document deleted")


@protected_router.post(
    "/questions",
    response_model=QuestionJobPublic,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["questions"],
)
async def create_question(
    body: QuestionRequest,
    request: Request,
    actor: CSRFUser,
    db: DBSession,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> QuestionJobPublic:
    key = idempotency_key or secrets.token_urlsafe(18)
    job, _duplicate, event_id = await request.app.state.question_service.create(
        db, actor, body.question, body.document_ids, key
    )
    await db.commit()
    if job.state == JobState.QUEUED:
        await request.app.state.outbox_dispatcher.dispatch_one(event_id)
    return await _question_public(db, job)


@protected_router.get("/questions", response_model=list[QuestionJobPublic], tags=["questions"])
async def list_questions(
    actor: CurrentUser,
    db: DBSession,
) -> list[QuestionJobPublic]:
    jobs = list(
        (
            await db.scalars(
                select(QuestionJob)
                .where(QuestionJob.requested_by_id == actor.id)
                .order_by(QuestionJob.created_at.desc())
                .limit(50)
            )
        ).all()
    )
    return [await _question_public(db, job) for job in jobs]


@protected_router.get("/questions/{job_id}", response_model=QuestionJobPublic, tags=["questions"])
async def get_question(
    job_id: uuid.UUID,
    actor: CurrentUser,
    db: DBSession,
) -> QuestionJobPublic:
    job = await question_repository.get(db, job_id, actor.id)
    if job is None:
        raise NotFoundError("Question")
    return await _question_public(db, job)


async def _question_public(db: AsyncSession, job: QuestionJob) -> QuestionJobPublic:
    answer = await db.scalar(select(Answer).where(Answer.question_job_id == job.id))
    public_answer: AnswerPublic | None = None
    if answer is not None:
        citations = list(
            (
                await db.scalars(
                    select(Citation)
                    .where(Citation.answer_id == answer.id)
                    .order_by(Citation.ordinal)
                )
            ).all()
        )
        public_answer = AnswerPublic(
            **AnswerPublic.model_validate(answer).model_dump(exclude={"citations"}),
            citations=[CitationPublic.model_validate(item) for item in citations],
        )
    return QuestionJobPublic(
        **QuestionJobPublic.model_validate(job).model_dump(exclude={"answer"}),
        answer=public_answer,
    )
