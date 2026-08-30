from __future__ import annotations

import pytest
from localguard_api.config import Settings
from pydantic import ValidationError

pytestmark = pytest.mark.unit


def test_deterministic_provider_is_rejected_outside_explicit_test_mode() -> None:
    with pytest.raises(ValidationError, match="deterministic providers"):
        Settings(
            app_env="development",
            allow_test_providers=False,
            ai_provider="deterministic",
            embedding_provider="deterministic",
        )


def test_deterministic_provider_requires_test_opt_in() -> None:
    settings = Settings(
        app_env="test",
        allow_test_providers=True,
        ai_provider="deterministic",
        embedding_provider="deterministic",
    )
    assert settings.ai_provider == "deterministic"


def test_production_requires_secure_session_cookie() -> None:
    with pytest.raises(ValidationError, match="SESSION_COOKIE_SECURE"):
        Settings(
            app_env="production",
            session_cookie_secure=False,
            allow_test_providers=False,
            ai_provider="ollama",
            embedding_provider="ollama",
        )


def test_mixed_provider_modes_are_rejected_instead_of_silently_selected() -> None:
    with pytest.raises(ValidationError, match="same runtime"):
        Settings(
            app_env="test",
            allow_test_providers=True,
            ai_provider="deterministic",
            embedding_provider="ollama",
        )


def test_model_lease_exceeds_http_timeout_by_safety_margin() -> None:
    with pytest.raises(ValidationError, match="exceed the HTTP timeout"):
        Settings(
            app_env="test",
            allow_test_providers=True,
            ai_provider="deterministic",
            embedding_provider="deterministic",
            model_http_timeout_seconds=180,
            model_lock_ttl_seconds=209,
        )


def test_default_model_timeout_and_lease_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MODEL_HTTP_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("MODEL_LOCK_TTL_SECONDS", raising=False)
    settings = Settings(_env_file=None)

    assert settings.model_http_timeout_seconds == 300
    assert settings.model_lock_ttl_seconds == 360


def test_allowed_hosts_parses_comma_separated_environment_value() -> None:
    settings = Settings(allowed_hosts="localhost, api,127.0.0.1")
    assert settings.allowed_hosts == ("localhost", "api", "127.0.0.1")
