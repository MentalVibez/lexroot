from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Import Base and all models so Alembic can diff against metadata
from db.database import ASYNC_DATABASE_URL, Base, _normalize_postgres_url
import db.models  # noqa: F401 — registers Word model on Base.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Prefer the async URL from the environment; fall back to alembic.ini value.
# For migrations we use asyncpg (same driver the app uses at runtime).
def _db_url() -> str:
    url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL") or ASYNC_DATABASE_URL
    if not url:
        url = config.get_main_option("sqlalchemy.url", "")
    return _normalize_postgres_url(url, async_driver=True)


def run_migrations_offline() -> None:
    url = _db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    async def _run() -> None:
        engine = create_async_engine(_db_url())
        async with engine.connect() as conn:
            await conn.run_sync(_do_run_migrations)
        await engine.dispose()

    asyncio.run(_run())


def _do_run_migrations(sync_conn) -> None:
    context.configure(connection=sync_conn, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
