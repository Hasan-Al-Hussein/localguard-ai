"""Password, opaque-session, CSRF, and normalization primitives."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import unicodedata
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65_536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_username(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    if not 3 <= len(normalized) <= 128:
        raise ValueError("username must contain between 3 and 128 characters")
    return normalized


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 1024:
        raise ValueError("password must contain between 12 and 1024 characters")
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(encoded, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def password_needs_rehash(encoded: str) -> bool:
    try:
        return _PASSWORD_HASHER.check_needs_rehash(encoded)
    except InvalidHashError:
        return True


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def verify_token_digest(token: str, expected: bytes) -> bool:
    return hmac.compare_digest(token_digest(token), expected)


def fingerprint(value: str) -> bytes:
    """Generate a non-reversible fixed-size operational fingerprint."""

    return hashlib.sha256(value.encode("utf-8", errors="replace")).digest()
