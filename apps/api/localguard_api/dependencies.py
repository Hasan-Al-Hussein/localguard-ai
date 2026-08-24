"""FastAPI dependency boundaries for database sessions, auth, CSRF, and RBAC."""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import AuthService
from .errors import AuthorizationError
from .models import Role, SessionToken, User


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async for session in request.app.state.database.session():
        yield session


def get_auth_service(request: Request) -> AuthService:
    return cast(AuthService, request.app.state.auth_service)


async def get_current_session(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> SessionToken:
    return await auth.authenticate(db, request.cookies.get(auth.settings.session_cookie_name))


async def get_current_user(
    session: Annotated[SessionToken, Depends(get_current_session)],
) -> User:
    return session.user


async def require_csrf(
    request: Request,
    session: Annotated[SessionToken, Depends(get_current_session)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    auth.verify_csrf(
        session,
        header_token=request.headers.get(auth.settings.csrf_header_name),
        cookie_token=request.cookies.get(auth.settings.csrf_cookie_name),
    )
    return session.user


def require_roles(*roles: Role, csrf: bool = False) -> Callable[..., Awaitable[User]]:
    dependency = require_csrf if csrf else get_current_user

    async def check(user: Annotated[User, Depends(dependency)]) -> User:
        if user.role not in roles:
            raise AuthorizationError()
        return user

    return check
