"""LangGraph checkpoint lifecycle with a JSON-only serializer policy."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from ..config import Settings


def strict_serializer() -> JsonPlusSerializer:
    """Allow primitives/containers only; never fall back to pickle or import classes."""

    return JsonPlusSerializer(
        pickle_fallback=False,
        allowed_json_modules=(),
        allowed_msgpack_modules=(),
    )


@asynccontextmanager
async def postgres_checkpointer(
    settings: Settings,
) -> AsyncIterator[AsyncPostgresSaver]:
    async with AsyncPostgresSaver.from_conn_string(
        settings.checkpoint_database_url,
        serde=strict_serializer(),
    ) as saver:
        yield saver


def in_memory_checkpointer() -> BaseCheckpointSaver[Any]:
    """Tests only; production callers must use ``postgres_checkpointer``."""

    return InMemorySaver(serde=strict_serializer())


async def setup_postgres_checkpoints(settings: Settings) -> None:
    """One-time deployment operation; application startup never calls setup()."""

    async with postgres_checkpointer(settings) as saver:
        await saver.setup()
