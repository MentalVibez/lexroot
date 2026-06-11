from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from api.main import app
from living_lexicon.config import LexiconConfig


def _production_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "https://pensiveape.com,https://www.pensiveape.com")
    monkeypatch.setenv("POSTGRES_PASSWORD", "not-the-default-secret")
    monkeypatch.setenv("ADMIN_API_TOKEN", "test-admin-token")
    monkeypatch.setenv("ENABLE_WRITE_ENDPOINTS", "false")


def test_production_allows_disabled_neo4j_with_default_password(monkeypatch):
    _production_env(monkeypatch)
    monkeypatch.setenv("ENABLE_NEO4J", "false")
    monkeypatch.setenv("NEO4J_PASSWORD", "lexicon_secret")

    LexiconConfig().validate_security()


def test_production_rejects_unsafe_neo4j_password_when_enabled(monkeypatch):
    _production_env(monkeypatch)
    monkeypatch.setenv("ENABLE_NEO4J", "true")
    monkeypatch.setenv("NEO4J_PASSWORD", "lexicon_secret")

    with pytest.raises(RuntimeError, match="unsafe NEO4J_PASSWORD"):
        LexiconConfig().validate_security()


def test_production_still_rejects_unsafe_postgres_and_cors(monkeypatch):
    _production_env(monkeypatch)
    monkeypatch.setenv("ENABLE_NEO4J", "false")
    monkeypatch.setenv("POSTGRES_PASSWORD", "lexicon_secret")

    with pytest.raises(RuntimeError, match="unsafe POSTGRES_PASSWORD"):
        LexiconConfig().validate_security()

    monkeypatch.setenv("POSTGRES_PASSWORD", "not-the-default-secret")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        LexiconConfig().validate_security()


class _FakeSession:
    def __init__(self, fail: bool = False):
        self.fail = fail

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, statement):
        assert str(statement) == str(text("SELECT 1"))
        if self.fail:
            raise RuntimeError("database unavailable")
        return None


async def test_health_marks_disabled_optional_services_ready_enough(monkeypatch):
    monkeypatch.setenv("ENABLE_NEO4J", "false")
    monkeypatch.setenv("ENABLE_OLLAMA", "false")

    import db.database
    monkeypatch.setattr(db.database, "AsyncSessionLocal", lambda: _FakeSession())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["neo4j"] == "disabled"
    assert data["ollama"] == "disabled"
    assert data["postgres"] == "ready"
    assert data["overall"] == "healthy"


async def test_health_degrades_when_postgres_unreachable_with_optional_services_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_NEO4J", "false")
    monkeypatch.setenv("ENABLE_OLLAMA", "false")

    import db.database
    monkeypatch.setattr(db.database, "AsyncSessionLocal", lambda: _FakeSession(fail=True))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["neo4j"] == "disabled"
    assert data["ollama"] == "disabled"
    assert data["postgres"] == "unreachable"
    assert data["overall"] == "degraded"


async def test_pg_routes_still_work_when_legacy_graph_is_disabled(app_client, write_headers, monkeypatch):
    monkeypatch.setenv("ENABLE_NEO4J", "false")

    await app_client.put("/pg/word", json={"word": "nice", "definition": "pleasant"}, headers=write_headers)
    await app_client.put("/pg/sense", json={
        "sense_id": "nice-me",
        "word": "nice",
        "definition": "Foolish; ignorant.",
        "era_name": "Middle English",
        "first_attested_year": 1290,
    }, headers=write_headers)

    word = await app_client.get("/pg/word/nice")
    timeline = await app_client.get("/pg/word/nice/era-timeline")
    era_words = await app_client.get("/pg/era/Middle English/words?limit=5")

    assert word.status_code == 200
    assert timeline.status_code == 200
    assert era_words.status_code == 200


async def test_legacy_graph_route_returns_503_when_disabled(app_client, monkeypatch):
    monkeypatch.setenv("ENABLE_NEO4J", "false")

    resp = await app_client.get("/word/nice")

    assert resp.status_code == 503
    assert "/pg/*" in resp.json()["detail"]
