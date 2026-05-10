"""
Shared pytest fixtures for HTTP endpoint tests and SDK unit tests.

HTTP fixtures use an in-memory CRUD stub so tests run without PostgreSQL,
Neo4j, Ollama, or an async SQLite driver.

SDK fixtures (in_memory_store, stub_historian) use living_lexicon.testing
utilities so tests run without Neo4j or Ollama.
"""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import db.models  # noqa: F401 — registers Word on Base.metadata
from api.deps import get_pg_session
from api.main import app
from db import crud
from living_lexicon.testing import InMemoryStore, WordHistorianFactory
from tests.factories import (
    AttestationPayloadFactory,
    EraTimelineFactory,
    SensePayloadFactory,
    WordPayloadFactory,
    WordSeedFactory,
)

@pytest_asyncio.fixture
async def app_client(monkeypatch):
    """AsyncClient wired to isolated in-memory CRUD functions."""
    # Prevent lifespan from connecting to Neo4j or validating prod secrets
    monkeypatch.setenv("APP_ENV", "development")

    words: dict[str, SimpleNamespace] = {}
    senses: dict[str, SimpleNamespace] = {}
    attestations: list[SimpleNamespace] = []
    ids = {"word": 0, "sense": 0, "attestation": 0}

    def _next_id(kind: str) -> int:
        ids[kind] += 1
        return ids[kind]

    async def fake_get_word(_session, word: str):
        return words.get(word.casefold())

    async def fake_count_words(_session):
        return len(words)

    async def fake_list_words(_session, offset: int = 0, limit: int = 50):
        ordered = sorted(words.values(), key=lambda row: row.word)
        return ordered[offset: offset + limit]

    async def fake_upsert_word(_session, word: str, **kwargs):
        key = word.casefold()
        existing = words.get(key)
        if existing is None:
            existing = SimpleNamespace(id=_next_id("word"), word=word)
            defaults = {
                "entry_type": "word",
                "phonemes": None,
                "etymology_root": None,
                "definition": None,
                "definition_source_slug": None,
                "definition_source_name": None,
                "definition_license": None,
                "origin_language": None,
                "language_family": None,
                "historical_context": None,
                "literal_meaning": None,
                "figurative_meaning": None,
                "example_usage": None,
                "semantic_drift_history": None,
            }
            for field, value in defaults.items():
                setattr(existing, field, value)
            words[key] = existing
        for field, value in kwargs.items():
            if value is not None:
                setattr(existing, field, value)
        return existing

    async def fake_search_words(_session, prefix: str, limit: int = 20):
        folded = prefix.casefold()
        matches = [row for key, row in words.items() if key.startswith(folded)]
        return sorted(matches, key=lambda row: row.word)[:limit]

    async def fake_get_sense(_session, sense_id: str):
        return senses.get(sense_id)

    async def fake_list_senses(_session, word: str):
        folded = word.casefold()
        rows = [row for row in senses.values() if row.word.casefold() == folded]
        return sorted(rows, key=lambda row: (row.first_attested_year or 999999, row.sense_id))

    async def fake_upsert_sense(_session, sense_id: str, **kwargs):
        existing = senses.get(sense_id)
        if existing is None:
            existing = SimpleNamespace(id=_next_id("sense"), sense_id=sense_id)
            defaults = {
                "word": "",
                "entry_type": "word",
                "part_of_speech": None,
                "definition": "",
                "meaning_type": "attested",
                "register": None,
                "domain": None,
                "era_name": None,
                "first_attested_year": None,
                "last_attested_year": None,
                "first_attested_source": None,
                "source_slug": None,
                "confidence": "medium",
                "confidence_reason": None,
                "evidence_grade": None,
                "citation": None,
                "page": None,
                "entry_headword": None,
                "source_url": None,
                "access_date": None,
                "review_status": None,
                "semantic_change_type": None,
                "origin_status": None,
                "usage_region": None,
                "usage_register": None,
                "notes": None,
            }
            for field, value in defaults.items():
                setattr(existing, field, value)
            senses[sense_id] = existing
        for field, value in kwargs.items():
            setattr(existing, field, value)
        return existing

    async def fake_add_attestation(_session, **kwargs):
        row = SimpleNamespace(id=_next_id("attestation"))
        defaults = {
            "sense_id": "",
            "word": "",
            "quote": None,
            "quote_year": None,
            "quote_author": None,
            "quote_work": None,
            "source_slug": None,
            "attestation_type": "historical_dictionary",
            "citation": None,
            "evidence_grade": None,
            "confidence_reason": None,
            "page": None,
            "entry_headword": None,
            "source_url": None,
            "access_date": None,
            "review_status": None,
            "notes": None,
        }
        for field, value in defaults.items():
            setattr(row, field, value)
        for field, value in kwargs.items():
            setattr(row, field, value)
        attestations.append(row)
        return row

    async def fake_list_attestations(_session, sense_id: str):
        rows = [row for row in attestations if row.sense_id == sense_id]
        return sorted(rows, key=lambda row: (row.quote_year or 999999, row.id))

    async def fake_bulk_get_senses_by_era(_session, words_list: list, era_name: str):
        out: dict[str, list] = {w: [] for w in words_list}
        for sense in senses.values():
            if sense.word in out and getattr(sense, "era_name", None) == era_name:
                out[sense.word].append(sense)
        return out

    async def fake_bulk_get_words(_session, words_list: list):
        return {w: words[w.casefold()] for w in words_list if w.casefold() in words}

    async def fake_list_senses_by_field(
        _session,
        domain=None,
        semantic_change_type=None,
        era_name=None,
        limit=50,
    ):
        results = []
        for sense in senses.values():
            if domain and getattr(sense, "domain", None) != domain:
                continue
            if semantic_change_type and getattr(sense, "semantic_change_type", None) != semantic_change_type:
                continue
            if era_name and getattr(sense, "era_name", None) != era_name:
                continue
            results.append(sense)
        return results[:limit]

    async def fake_list_senses_by_review_status(
        _session, review_status: str, word: str | None = None, offset: int = 0, limit: int = 50
    ):
        results = [
            s for s in senses.values()
            if getattr(s, "review_status", None) == review_status
            and (word is None or s.word == word)
        ]
        return results[offset : offset + limit]

    async def fake_update_sense_review_status(_session, sense_id: str, review_status: str, reviewer_notes=None):
        sense = senses.get(sense_id)
        if sense is None:
            return None
        sense.review_status = review_status
        if reviewer_notes is not None:
            sense.reviewer_notes = reviewer_notes
        return sense

    monkeypatch.setattr(crud, "get_word", fake_get_word)
    monkeypatch.setattr(crud, "count_words", fake_count_words)
    monkeypatch.setattr(crud, "list_words", fake_list_words)
    monkeypatch.setattr(crud, "upsert_word", fake_upsert_word)
    monkeypatch.setattr(crud, "search_words", fake_search_words)
    monkeypatch.setattr(crud, "get_sense", fake_get_sense)
    monkeypatch.setattr(crud, "list_senses", fake_list_senses)
    monkeypatch.setattr(crud, "upsert_sense", fake_upsert_sense)
    monkeypatch.setattr(crud, "add_attestation", fake_add_attestation)
    monkeypatch.setattr(crud, "list_attestations", fake_list_attestations)
    word_relations: list[SimpleNamespace] = []
    morphemes: list[SimpleNamespace] = []

    async def fake_get_word_relations(_session, word: str, relation_type=None):
        return [
            r for r in word_relations
            if r.from_word == word and (relation_type is None or r.relation_type == relation_type)
        ]

    async def fake_add_word_relation(_session, from_word, to_word, relation_type, **kwargs):
        row = SimpleNamespace(
            id=_next_id("sense"),
            from_word=from_word,
            to_word=to_word,
            relation_type=relation_type,
            era_name=kwargs.get("era_name"),
            source_slug=kwargs.get("source_slug"),
            confidence=kwargs.get("confidence", "medium"),
            notes=kwargs.get("notes"),
        )
        word_relations.append(row)
        return row

    async def fake_get_word_family(_session, root_word: str, depth=3, limit=50):
        related = {
            r.to_word for r in word_relations
            if r.from_word == root_word and r.relation_type in ("derived_from", "root_of")
        }
        return sorted(related)[:limit]

    async def fake_get_morphemes(_session, word: str):
        return [m for m in morphemes if m.word == word]

    async def fake_find_words_by_morpheme(_session, morpheme: str, role=None, limit=50):
        return [
            m.word for m in morphemes
            if m.morpheme == morpheme and (role is None or m.role == role)
        ][:limit]

    monkeypatch.setattr(crud, "bulk_get_senses_by_era", fake_bulk_get_senses_by_era)
    monkeypatch.setattr(crud, "bulk_get_words", fake_bulk_get_words)
    monkeypatch.setattr(crud, "list_senses_by_field", fake_list_senses_by_field)
    monkeypatch.setattr(crud, "list_senses_by_review_status", fake_list_senses_by_review_status)
    monkeypatch.setattr(crud, "update_sense_review_status", fake_update_sense_review_status)
    monkeypatch.setattr(crud, "get_word_relations", fake_get_word_relations)
    monkeypatch.setattr(crud, "add_word_relation", fake_add_word_relation)
    monkeypatch.setattr(crud, "get_word_family", fake_get_word_family)
    monkeypatch.setattr(crud, "get_morphemes", fake_get_morphemes)
    monkeypatch.setattr(crud, "find_words_by_morpheme", fake_find_words_by_morpheme)

    async def _override():
        yield None

    app.dependency_overrides[get_pg_session] = _override

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def write_headers(monkeypatch):
    """Environment + headers for write endpoints that require admin auth."""
    monkeypatch.setenv("ENABLE_WRITE_ENDPOINTS", "true")
    monkeypatch.setenv("ADMIN_API_TOKEN", "test-token")
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def contributor_headers(monkeypatch):
    """Environment + headers for contributor submission endpoints."""
    monkeypatch.setenv("CONTRIBUTOR_API_TOKEN", "contrib-token")
    return {"Authorization": "Bearer contrib-token"}


# ---------------------------------------------------------------------------
# SDK unit-test fixtures — zero external dependencies
# ---------------------------------------------------------------------------

@pytest.fixture
def word_seed():
    """A single 'prevent' word seed dict for InMemoryStore."""
    return WordSeedFactory.build(
        name="prevent",
        definition="To stop something from happening.",
        root="praevenire",
        root_meaning="to come before; to precede",
        root_origin="Latin",
    )


@pytest.fixture
def in_memory_store(word_seed):
    """InMemoryStore pre-loaded with 'prevent' and a two-era timeline."""
    timeline = EraTimelineFactory.build_timeline(
        "prevent",
        {
            "Middle English": "to come before; to precede",
            "Early Modern English": "to hinder or obstruct",
        },
    )
    return InMemoryStore(
        words={"prevent": word_seed},
        era_timelines=timeline,
    )


@pytest.fixture
def stub_historian(in_memory_store):
    """WordHistorian backed by InMemoryStore and a stub LLM."""
    return WordHistorianFactory.build(
        store=in_memory_store,
        llm_response="The word 'prevent' originally meant 'to come before'.",
    )


@pytest.fixture
def word_payload():
    """Return the WordPayloadFactory class for use in HTTP endpoint tests."""
    return WordPayloadFactory


@pytest.fixture
def sense_payload():
    """Return the SensePayloadFactory class for use in HTTP endpoint tests."""
    return SensePayloadFactory


@pytest.fixture
def attestation_payload():
    """Return the AttestationPayloadFactory class for use in HTTP endpoint tests."""
    return AttestationPayloadFactory
