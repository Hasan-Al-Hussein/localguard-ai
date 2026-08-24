"""Opaque bearer verification backed by hashed PostgreSQL credentials."""

from __future__ import annotations

from typing import cast

from fastmcp.server.auth import AccessToken, TokenVerifier
from localguard_api.database import Database
from localguard_api.models import MCPAccessToken, utc_now
from localguard_api.security import token_digest
from sqlalchemy import select
from sqlalchemy.orm import joinedload


class DatabaseTokenVerifier(TokenVerifier):
    def __init__(self, database: Database) -> None:
        super().__init__(required_scopes=["localguard:mcp"])
        self.database = database

    async def verify_token(self, token: str) -> AccessToken | None:
        if not 20 <= len(token) <= 256:
            return None
        async with self.database.sessions() as db:
            row = cast(
                MCPAccessToken | None,
                await db.scalar(
                    select(MCPAccessToken)
                    .options(joinedload(MCPAccessToken.user))
                    .where(MCPAccessToken.token_hash == token_digest(token))
                ),
            )
            now = utc_now()
            if (
                row is None
                or row.revoked_at is not None
                or (row.expires_at is not None and row.expires_at <= now)
                or not row.user.is_active
            ):
                return None
            expires_at = int(row.expires_at.timestamp()) if row.expires_at else None
            return AccessToken(
                token=token,
                client_id=f"localguard:{row.id}",
                subject=str(row.user.id),
                scopes=["localguard:mcp"],
                expires_at=expires_at,
                claims={
                    "user_id": str(row.user.id),
                    "username": row.user.username,
                    "role": row.user.role.value,
                },
            )
