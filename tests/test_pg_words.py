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


async def test_get_word_is_case_insensitive(app_client, write_headers):
    await _upsert(app_client, write_headers, word="Invisible")

    resp = await app_client.get("/pg/word/invisible")
    assert resp.status_code == 200
    assert resp.json()["word"] == "Invisible"

    resp = await app_client.get("/pg/word/INVISIBLE")
    assert resp.status_code == 200
    assert resp.json()["word"] == "Invisible"


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


async def test_suggest_words_returns_likely_typo_correction(app_client, write_headers):
    await _upsert(app_client, write_headers, word="invisible")
    await _upsert(app_client, write_headers, word="invincible")
    await _upsert(app_client, write_headers, word="banana")

    resp = await app_client.get("/pg/words/suggest?q=invisable")
    assert resp.status_code == 200
    words = [r["word"] for r in resp.json()]
    assert words[0] == "invisible"
    assert "banana" not in words


async def test_suggest_words_returns_empty_for_unrelated_query(app_client, write_headers):
    await _upsert(app_client, write_headers, word="invisible")

    resp = await app_client.get("/pg/words/suggest?q=zzzzzzzz")
    assert resp.status_code == 200
    assert resp.json() == []


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


async def test_vitality_shape(app_client, write_headers):
    await _upsert(app_client, write_headers, word="awful")
    await app_client.put("/pg/sense", json={
        "sense_id": "awful-oe-1",
        "word": "awful",
        "definition": "Inspiring awe or dread.",
        "first_attested_year": 1000,
        "last_attested_year": 1300,
        "evidence_grade": "B",
        "semantic_change_type": "pejoration",
    }, headers=write_headers)

    resp = await app_client.get("/pg/word/awful/vitality")
    assert resp.status_code == 200
    data = resp.json()
    assert data["word"] == "awful"
    assert isinstance(data["vitality_score"], float)
    assert 0.0 <= data["vitality_score"] <= 1.0
    m = data["metrics"]
    assert {"stability", "drift_velocity", "attestation_recency", "sense_count", "status"} <= set(m.keys())


async def test_vitality_word_not_found(app_client):
    resp = await app_client.get("/pg/word/nonexistent/vitality")
    assert resp.status_code == 404


async def test_era_check_flags_anachronism(app_client, write_headers):
    await _upsert(app_client, write_headers, word="prevent", definition="To come before.")
    await app_client.put("/pg/sense", json={
        "sense_id": "prevent-me-1",
        "word": "prevent",
        "definition": "To come before; to precede.",
        "era_name": "Middle English",
        "first_attested_year": 1350,
    }, headers=write_headers)

    resp = await app_client.post("/pg/word/era-check", json={
        "text": "He tried to prevent the procession from reaching the cathedral.",
        "era_name": "Middle English",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["era_name"] == "Middle English"
    assert data["words_checked"] > 0
    flagged_words = [f["word"] for f in data["flagged"]]
    assert "prevent" in flagged_words


async def test_era_check_scans_all_eras_when_era_omitted(app_client, write_headers):
    await _upsert(app_client, write_headers, word="nice", definition="agreeable; precise.")
    await app_client.put("/pg/sense", json={
        "sense_id": "nice-me-1",
        "word": "nice",
        "definition": "Foolish; ignorant.",
        "era_name": "Middle English",
        "first_attested_year": 1290,
        "last_attested_year": 1450,
        "source_slug": "mec-corpus",
        "confidence": "high",
    }, headers=write_headers)
    # A second, later era for the same word — the scan should pick the earliest.
    await app_client.put("/pg/sense", json={
        "sense_id": "nice-eme-1",
        "word": "nice",
        "definition": "Precise; fastidious.",
        "era_name": "Early Modern English",
        "first_attested_year": 1560,
    }, headers=write_headers)

    # No era_name at all -> scan every era.
    resp = await app_client.post("/pg/word/era-check", json={
        "text": "What a nice remark.",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["era_name"] == "All eras"
    flagged = {f["word"]: f for f in data["flagged"]}
    assert "nice" in flagged
    entry = flagged["nice"]
    # Earliest sense wins and the word is labelled with its own era + metadata.
    assert entry["era_name"] == "Middle English"
    assert entry["first_attested_year"] == 1290
    assert entry["era_source"] == "mec-corpus"
    assert entry["confidence"] == "high"
    assert entry["modern_definition"] == "agreeable; precise."


async def test_pg_era_timeline_builds_from_senses(app_client, write_headers):
    await _upsert(app_client, write_headers, word="nice", definition="pleasant; agreeable.")
    await app_client.put("/pg/sense", json={
        "sense_id": "nice-me", "word": "nice", "definition": "Foolish; ignorant.",
        "era_name": "Middle English", "first_attested_year": 1290, "last_attested_year": 1450,
    }, headers=write_headers)
    await app_client.put("/pg/sense", json={
        "sense_id": "nice-lme", "word": "nice", "definition": "Pleasant; kind.",
        "era_name": "Late Modern English", "first_attested_year": 1769,
    }, headers=write_headers)
    # A sense with no era should be skipped, not crash.
    await app_client.put("/pg/sense", json={
        "sense_id": "nice-x", "word": "nice", "definition": "Undated.",
    }, headers=write_headers)

    resp = await app_client.get("/pg/word/nice/era-timeline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["word"] == "nice"
    eras = [e["era_name"] for e in data["timeline"]]
    assert eras == ["Middle English", "Late Modern English"]
    first = data["timeline"][0]
    assert first["era_start"] == 1290
    assert first["era_end"] == 1450
    assert first["meaning"] == "Foolish; ignorant."


async def test_pg_era_timeline_empty_for_unknown_word(app_client, write_headers):
    resp = await app_client.get("/pg/word/nonexistentword/era-timeline")
    assert resp.status_code == 200
    assert resp.json() == {"word": "nonexistentword", "timeline": []}


async def test_pg_word_in_era_returns_sourced_summary(app_client, write_headers):
    await _upsert(app_client, write_headers, word="prevent", definition="to stop beforehand.")
    await app_client.put("/pg/sense", json={
        "sense_id": "prevent-me", "word": "prevent", "definition": "To come before; to precede.",
        "era_name": "Middle English", "first_attested_year": 1350, "source_slug": "mec-corpus",
    }, headers=write_headers)

    resp = await app_client.get("/pg/word/prevent/era/Middle English")
    assert resp.status_code == 200
    data = resp.json()
    assert data["historical_meaning"] == "To come before; to precede."
    assert data["modern_definition"] == "to stop beforehand."
    assert data["era_source"] == "mec-corpus"
    assert "Middle English" in data["ai_explanation"]
    assert "mec-corpus" in data["ai_explanation"]


async def test_pg_word_in_era_unknown_era_degrades_gracefully(app_client, write_headers):
    await _upsert(app_client, write_headers, word="prevent", definition="to stop beforehand.")
    resp = await app_client.get("/pg/word/prevent/era/Old English")
    assert resp.status_code == 200
    data = resp.json()
    assert data["historical_meaning"] is None
    assert data["modern_definition"] == "to stop beforehand."
    assert data["ai_explanation"] is None


async def test_pg_era_words_lists_words_in_era(app_client, write_headers):
    await _upsert(app_client, write_headers, word="nice", definition="pleasant.")
    await app_client.put("/pg/sense", json={
        "sense_id": "nice-me", "word": "nice", "definition": "Foolish.",
        "era_name": "Middle English", "first_attested_year": 1290,
    }, headers=write_headers)
    await _upsert(app_client, write_headers, word="silly", definition="foolish.")
    await app_client.put("/pg/sense", json={
        "sense_id": "silly-me", "word": "silly", "definition": "Innocent; blessed.",
        "era_name": "Middle English", "first_attested_year": 1200,
    }, headers=write_headers)

    resp = await app_client.get("/pg/era/Middle English/words?limit=20")
    assert resp.status_code == 200
    data = resp.json()
    assert data["era"] == "Middle English"
    names = {w["name"]: w for w in data["words"]}
    assert "nice" in names and "silly" in names
    assert names["nice"]["historical_meaning"] == "Foolish."
    assert names["nice"]["modern_definition"] == "pleasant."


async def test_era_check_auto_sentinel_scans_all_eras(app_client, write_headers):
    await _upsert(app_client, write_headers, word="silly", definition="foolish.")
    await app_client.put("/pg/sense", json={
        "sense_id": "silly-me-1",
        "word": "silly",
        "definition": "Innocent; deserving compassion.",
        "era_name": "Middle English",
        "first_attested_year": 1200,
    }, headers=write_headers)

    # An explicit "auto" sentinel is treated the same as omitting era_name.
    resp = await app_client.post("/pg/word/era-check", json={
        "text": "The silly child.",
        "era_name": "auto",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["era_name"] == "All eras"
    assert "silly" in [f["word"] for f in data["flagged"]]
