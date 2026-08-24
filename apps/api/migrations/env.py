"""Alembic environment for LocalGuard's async PostgreSQL database."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from localguard_api.config import get_settings
from localguard_api.models import Base
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata

LANGGRAPH_MANAGED_OBJECTS = frozenset(
    {
        "checkpoint_migrations",
        "checkpoints",
        "checkpoint_blobs",
        "checkpoint_writes",
        "checkpoints_thread_id_idx",
        "checkpoint_blobs_thread_id_idx",
        "checkpoint_writes_thread_id_idx",
    }
)


def include_object(
    database_object: object,
    name: str | None,
    object_type: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    """Leave LangGraph's versioned checkpoint schema to its own setup routine."""

    del database_object, compare_to
    return not (
        reflected and object_type in {"table", "index"} and name in LANGGRAPH_MANAGED_OBJECTS
    )


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure one synchronous migration context on an async connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations through SQLAlchemy's async psycopg dialect."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
