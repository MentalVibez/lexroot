"""
Shared pytest fixtures for HTTP endpoint tests.

Uses an in-memory SQLite database via aiosqlite so tests run without a
live PostgreSQL instance. SQLAlchemy maps JSONB → JSON automatically on
SQLite — no manual workarounds needed.

The `app_client` fixture overrides the FastAPI `get_pg_session` dependency
so every test gets a fresh, isolated database.
"""
from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import db.models  # noqa: F401 — registers Word on Base.metadata
from api.deps import get_pg_session
from api.main import app
from db.database import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def app_client(monkeypatch):
    """AsyncClient wired to an isolated in-memory SQLite database."""
    # Prevent lifespan from connecting to Neo4j or validating prod secrets
    monkeypatch.setenv("APP_ENV", "development")

    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_pg_session] = _override

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def write_headers(monkeypatch):
    """Environment + headers for write endpoints that require admin auth."""
    monkeypatch.setenv("ENABLE_WRITE_ENDPOINTS", "true")
    monkeypatch.setenv("ADMIN_API_TOKEN", "test-token")
    return {"Authorization": "Bearer test-token"}
