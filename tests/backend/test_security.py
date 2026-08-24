from __future__ import annotations

import pytest
from localguard_api.security import (
    hash_password,
    new_opaque_token,
    normalize_username,
    token_digest,
    verify_password,
    verify_token_digest,
)

pytestmark = [pytest.mark.unit, pytest.mark.security]


def test_argon2id_password_round_trip_does_not_store_plaintext() -> None:
    password = "correct horse battery staple"
    encoded = hash_password(password)
    assert encoded.startswith("$argon2id$")
    assert password not in encoded
    assert verify_password(password, encoded)
    assert not verify_password("incorrect password", encoded)


def test_opaque_tokens_are_random_and_stored_only_as_digests() -> None:
    first = new_opaque_token()
    second = new_opaque_token()
    assert first != second
    assert len(token_digest(first)) == 32
    assert verify_token_digest(first, token_digest(first))
    assert not verify_token_digest(second, token_digest(first))


def test_username_normalization_is_unicode_aware() -> None:
    assert normalize_username("  ReviewER  ") == "reviewer"


@pytest.mark.parametrize("value", ["", "ab", "x" * 129])
def test_username_normalization_rejects_invalid_lengths(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_username(value)
