"""HTTP endpoint tests for historical sense and attestation routes."""
from __future__ import annotations


async def test_sense_roundtrip_and_word_listing(app_client, write_headers):
    payload = {
        "sense_id": "nice-adj-1300-ignorant",
        "word": "nice",
        "entry_type": "word",
        "part_of_speech": "adjective",
        "definition": "Foolish or ignorant.",
        "meaning_type": "attested",
        "register": "obsolete",
        "domain": "general",
        "era_name": "Middle English",
        "first_attested_year": 1300,
        "last_attested_year": 1500,
        "source_slug": "middle-english-dictionary",
        "confidence": "high",
        "confidence_reason": "Historical dictionary evidence with citation.",
        "evidence_grade": "B",
        "citation": "MED nice adj.",
        "entry_headword": "nice",
        "semantic_change_type": "pejoration",
        "origin_status": "attested",
        "usage_region": "England",
        "usage_register": "obsolete",
        "notes": "Compact source-backed note.",
    }

    resp = await app_client.put("/pg/sense", json=payload, headers=write_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["sense_id"] == "nice-adj-1300-ignorant"
    assert data["definition"] == "Foolish or ignorant."
    assert data["first_attested_year"] == 1300
    assert data["evidence_grade"] == "B"
    assert data["semantic_change_type"] == "pejoration"

    by_id = await app_client.get("/pg/sense/nice-adj-1300-ignorant")
    assert by_id.status_code == 200
    assert by_id.json()["era_name"] == "Middle English"

    by_word = await app_client.get("/pg/word/nice/senses")
    assert by_word.status_code == 200
    rows = by_word.json()
    assert len(rows) == 1
    assert rows[0]["confidence"] == "high"


async def test_attestation_roundtrip(app_client, write_headers):
    sense_payload = {
        "sense_id": "silly-adj-1200-blessed",
        "word": "silly",
        "definition": "Blessed or happy.",
        "era_name": "Middle English",
        "first_attested_year": 1200,
        "source_slug": "middle-english-dictionary",
        "confidence": "high",
        "confidence_reason": "Historical dictionary evidence with citation.",
        "evidence_grade": "B",
        "citation": "MED silly adj.",
    }
    resp = await app_client.put("/pg/sense", json=sense_payload, headers=write_headers)
    assert resp.status_code == 200, resp.text

    attestation_payload = {
        "sense_id": "silly-adj-1200-blessed",
        "word": "silly",
        "quote": "A compact source quotation.",
        "quote_year": 1225,
        "quote_author": "unknown",
        "quote_work": "early Middle English source",
        "source_slug": "middle-english-dictionary",
        "attestation_type": "quotation",
        "citation": "MED silly adj.",
        "evidence_grade": "A",
        "confidence_reason": "Primary dated quotation.",
        "entry_headword": "silly",
        "review_status": "reviewed",
        "notes": "Supports the earlier positive sense.",
    }
    created = await app_client.post(
        "/pg/attestation",
        json=attestation_payload,
        headers=write_headers,
    )
    assert created.status_code == 200, created.text
    assert created.json()["quote_year"] == 1225
    assert created.json()["evidence_grade"] == "A"

    listed = await app_client.get("/pg/sense/silly-adj-1200-blessed/attestations")
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["attestation_type"] == "quotation"


async def test_sense_write_requires_auth(app_client):
    resp = await app_client.put(
        "/pg/sense",
        json={
            "sense_id": "secret-sense",
            "word": "secret",
            "definition": "Hidden from public writes.",
        },
    )
    assert resp.status_code == 404
