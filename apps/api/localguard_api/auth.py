"""Opaque server-side session authentication service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings
from .errors import AuthenticationError
from .models import SessionToken, User
from .repositories import AuthRepository, auth_repository
from .security import (
    fingerprint,
    hash_password,
    new_opaque_token,
    normalize_username,
    password_needs_rehash,
    token_digest,
    utc_now,
    verify_password,
    verify_token_digest,
)

_DUMMY_PASSWORD_HASH = hash_password("localguard-dummy-password-never-used")


@dataclass(frozen=True, slots=True)
class IssuedSession:
    user: User
    session_token: str
    csrf_token: str
    expires_at: datetime


class AuthService:
    def __init__(self, settings: Settings, repository: AuthRepository = auth_repository) -> None:
        self.settings = settings
        self.repository = repository

    async def login(
        self,
        db: AsyncSession,
        *,
        username: str,
        password: str,
        user_agent: str | None,
    ) -> IssuedSession:
        try:
            principal = normalize_username(username)
        except ValueError as exc:
            raise AuthenticationError("Invalid username or password") from exc
        now = utc_now()
        if await self.repository.login_is_blocked(db, principal, now):
            raise AuthenticationError("Sign-in temporarily unavailable; try again later")

        user = await self.repository.find_user(db, principal)
        valid = verify_password(password, user.password_hash if user else _DUMMY_PASSWORD_HASH)
        if user is None or not valid or not user.is_active:
            await self.repository.record_login_failure(
                db,
                principal,
                now=now,
                window_seconds=self.settings.login_window_seconds,
                max_failures=self.settings.login_max_failures,
            )
            await db.commit()
            raise AuthenticationError("Invalid username or password")

        await self.repository.clear_login_failures(db, principal)
        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        session_token = new_opaque_token()
        csrf_token = new_opaque_token()
        expires_at = now + timedelta(minutes=self.settings.session_ttl_minutes)
        row = SessionToken(
            user_id=user.id,
            token_hash=token_digest(session_token),
            csrf_hash=token_digest(csrf_token),
            expires_at=expires_at,
            last_seen_at=now,
            user_agent_hash=fingerprint(user_agent) if user_agent else None,
        )
        await self.repository.create_session(db, row)
        return IssuedSession(user, session_token, csrf_token, expires_at)

    async def authenticate(self, db: AsyncSession, raw_token: str | None) -> SessionToken:
        if not raw_token or len(raw_token) > 256:
            raise AuthenticationError()
        row = await self.repository.get_session(db, token_digest(raw_token))
        now = utc_now()
        if (
            row is None
            or row.revoked_at is not None
            or row.expires_at <= now
            or not row.user.is_active
        ):
            raise AuthenticationError()
        row.last_seen_at = now
        return row

    async def logout(self, db: AsyncSession, raw_token: str | None) -> None:
        if raw_token:
            await self.repository.revoke_session(db, token_digest(raw_token), utc_now())

    def verify_csrf(
        self,
        session: SessionToken,
        *,
        header_token: str | None,
        cookie_token: str | None,
    ) -> None:
        if (
            not header_token
            or not cookie_token
            or len(header_token) > 256
            or len(cookie_token) > 256
            or not verify_token_digest(header_token, session.csrf_hash)
            or not verify_token_digest(cookie_token, session.csrf_hash)
        ):
            raise AuthenticationError("Invalid CSRF token")

    def rotate_csrf(self, session: SessionToken) -> str:
        token = new_opaque_token()
        session.csrf_hash = token_digest(token)
        return token
