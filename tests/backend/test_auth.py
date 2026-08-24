from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from localguard_api.auth import AuthService
from localguard_api.config import Settings
from localguard_api.errors import AuthenticationError
from localguard_api.models import Role, SessionToken, User
from localguard_api.security import hash_password, token_digest, utc_now

pytestmark = [pytest.mark.unit, pytest.mark.security]


@dataclass
class FakeDB:
    commits: int = 0

    async def commit(self) -> None:
        self.commits += 1


class FakeAuthRepository:
    def __init__(self, user: User | None) -> None:
        self.user = user
        self.failures = 0
        self.session: SessionToken | None = None

    async def login_is_blocked(self, db: object, principal: str, now: object) -> bool:
        del db, principal, now
        return False

    async def find_user(self, db: object, username: str) -> User | None:
        del db, username
        return self.user

    async def record_login_failure(self, db: object, principal: str, **kwargs: object) -> None:
        del db, principal, kwargs
        self.failures += 1

    async def clear_login_failures(self, db: object, principal: str) -> None:
        del db, principal

    async def create_session(self, db: object, session: SessionToken) -> SessionToken:
        del db
        self.session = session
        return session


def _settings() -> Settings:
    return Settings(app_env="test", allow_test_providers=True)


@pytest.mark.asyncio
async def test_login_issues_opaque_session_and_csrf_pair() -> None:
    user = User(
        id=uuid.uuid4(),
        username="reviewer",
        display_name="Reviewer",
        role=Role.REVIEWER,
        password_hash=hash_password("a sufficiently long password"),
        is_active=True,
    )
    repository = FakeAuthRepository(user)
    service = AuthService(_settings(), repository=repository)  # type: ignore[arg-type]
    issued = await service.login(
        FakeDB(),
        username="Reviewer",
        password="a sufficiently long password",
        user_agent="pytest",
    )
    assert issued.user is user
    assert repository.session is not None
    assert repository.session.token_hash == token_digest(issued.session_token)
    service.verify_csrf(
        repository.session,
        header_token=issued.csrf_token,
        cookie_token=issued.csrf_token,
    )


@pytest.mark.asyncio
async def test_failed_login_records_and_commits_throttle_state() -> None:
    repository = FakeAuthRepository(None)
    database = FakeDB()
    service = AuthService(_settings(), repository=repository)  # type: ignore[arg-type]
    with pytest.raises(AuthenticationError, match="Invalid username or password"):
        await service.login(
            database,
            username="unknown",
            password="not the password",
            user_agent=None,
        )
    assert repository.failures == 1
    assert database.commits == 1


def test_csrf_requires_matching_header_cookie_and_session_digest() -> None:
    service = AuthService(_settings(), repository=FakeAuthRepository(None))  # type: ignore[arg-type]
    session = SessionToken(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        token_hash=token_digest("session"),
        csrf_hash=token_digest("expected-csrf"),
        created_at=utc_now(),
        expires_at=utc_now(),
        last_seen_at=utc_now(),
    )
    with pytest.raises(AuthenticationError, match="CSRF"):
        service.verify_csrf(
            session,
            header_token="attacker-token",
            cookie_token="expected-csrf",
        )
