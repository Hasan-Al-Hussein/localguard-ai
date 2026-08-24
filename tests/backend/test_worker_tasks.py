"""Celery retry-boundary regressions for durable worker adapters."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import pytest
from localguard_api.database import Database
from localguard_api.errors import RetryableServiceUnavailableError, ServiceUnavailableError
from localguard_api.providers import ChatProvider, EmbeddingProvider
from localguard_worker import tasks

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("error", "expected_attempts"),
    [
        (
            ServiceUnavailableError(
                "model_schema_invalid", "The local model returned invalid output"
            ),
            1,
        ),
        (
            RetryableServiceUnavailableError(
                "generation_transport_failed", "The local model transport failed"
            ),
            4,
        ),
    ],
)
def test_worker_autoretry_is_limited_to_typed_transient_errors(
    monkeypatch: pytest.MonkeyPatch,
    error: ServiceUnavailableError,
    expected_attempts: int,
) -> None:
    attempts = 0

    async def fail(
        _operation: Callable[
            [Database, ChatProvider, EmbeddingProvider],
            Awaitable[bool],
        ],
        _outbox_event_id: uuid.UUID | None,
    ) -> bool:
        nonlocal attempts
        attempts += 1
        raise error

    monkeypatch.setattr(tasks, "_with_runtime", fail)

    result = tasks.answer_question.apply(args=[str(uuid.uuid4())], throw=False)

    assert result.failed()
    assert attempts == expected_attempts
