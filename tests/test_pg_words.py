"""HTTP endpoint tests for the /pg/* word routes."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _upsert(client, headers, **kwargs):
    payload = {"word": "testword", **kwargs}
    resp = await client.put("/pg/word", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_list_returns_pagination_envelope(app_client):
    resp = await app_client.get("/pg/words")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) >= {"items", "total", "offset", "limit"}
    assert data["items"] == []
    assert data["total"] == 0
    assert data["offset"] == 0
    assert data["limit"] == 50


async def test_get_word_not_found(app_client):
    resp = await app_client.get("/pg/word/zzznonsense")
    assert resp.status_code == 404


async def test_upsert_and_get_roundtrip(app_client, write_headers):
    await _upsert(
        app_client, write_headers,
        word="Charity",
        phonemes="/ˈtʃær.ɪ.ti/",
        etymology_root="caritas",
        definition="Voluntary giving to those in need.",
        origin_language="Latin",
        language_family="Indo-European (Italic)",
        historical_context="From Latin caritas (dearness, love).",
    )
    resp = await app_client.get("/pg/word/Charity")
    assert resp.status_code == 200
    data = resp.json()
    assert data["word"] == "Charity"
    assert data["phonemes"] == "/ˈtʃær.ɪ.ti/"
    assert data["definition"] == "Voluntary giving to those in need."
    assert data["origin_language"] == "Latin"
    assert data["language_family"] == "Indo-European (Italic)"
    assert data["historical_context"] == "From Latin caritas (dearness, love)."


async def test_upsert_backward_compat_without_enrichment_fields(app_client, write_headers):
    """PUT with only word + phonemes must still succeed; new fields default to null."""
    data = await _upsert(app_client, write_headers, word="Simple", phonemes="/ˈsɪm.pəl/")
    assert data["definition"] is None
    assert data["origin_language"] is None
    assert data["language_family"] is None
    assert data["historical_context"] is None


async def test_list_pagination(app_client, write_headers):
    for w in ("Apple", "Banana", "Cherry"):
        await _upsert(app_client, write_headers, word=w)

    resp = await app_client.get("/pg/words?limit=2&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["offset"] == 0
    assert data["limit"] == 2

    resp2 = await app_client.get("/pg/words?limit=2&offset=2")
    data2 = resp2.json()
    assert data2["total"] == 3
    assert len(data2["items"]) == 1


async def test_search_prefix(app_client, write_headers):
    for w in ("Charity", "Charitable", "Charcoal"):
        await _upsert(app_client, write_headers, word=w)

    resp = await app_client.get("/pg/words/search?q=Char")
    assert resp.status_code == 200
    words = {r["word"] for r in resp.json()}
    assert {"Charity", "Charitable", "Charcoal"} == words


async def test_upsert_coalesces_on_second_call(app_client, write_headers):
    """A second PUT without definition must not overwrite the existing definition."""
    await _upsert(
        app_client, write_headers,
        word="Grace",
        definition="Elegance and beauty of form or movement.",
        origin_language="Latin",
    )
    # Second upsert: update phonemes only, omit definition
    await _upsert(app_client, write_headers, word="Grace", phonemes="/ɡreɪs/")

    resp = await app_client.get("/pg/word/Grace")
    data = resp.json()
    assert data["phonemes"] == "/ɡreɪs/"
    assert data["definition"] == "Elegance and beauty of form or movement."
    assert data["origin_language"] == "Latin"


async def test_upsert_requires_auth(app_client):
    """PUT without a valid token must be blocked."""
    resp = await app_client.put("/pg/word", json={"word": "Secret"})
    # ENABLE_WRITE_ENDPOINTS=false (default) → 404; endpoints hidden
    assert resp.status_code == 404
