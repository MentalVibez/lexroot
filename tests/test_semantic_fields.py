"""Tests for semantic field query, comparative drift, and drift trajectory endpoints."""
from __future__ import annotations

import pytest


async def _put_sense(client, headers, **kwargs):
    payload = {
        "sense_id": "test-sense-1",
        "word": "prevent",
        "definition": "To hinder or stop.",
        **kwargs,
    }
    resp = await client.put("/pg/sense", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Semantic field query
# ---------------------------------------------------------------------------

async def test_semantic_field_filter_by_domain(app_client, write_headers):
    await _put_sense(
        app_client, write_headers,
        sense_id="prevent-law-1",
        word="prevent",
        definition="To hinder a legal action.",
        domain="law",
        semantic_change_type="narrowing",
        era_name="Early Modern English",
        evidence_grade="B",
        first_attested_year=1550,
    )
    resp = await app_client.get("/pg/semantic-fields?domain=law")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["filters"] == {"domain": "law"}
    words = [s["word"] for s in data["senses"]]
    assert "prevent" in words


async def test_semantic_field_requires_at_least_one_filter(app_client):
    resp = await app_client.get("/pg/semantic-fields")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Comparative drift
# ---------------------------------------------------------------------------

async def test_drift_compare_two_words(app_client, write_headers):
    for word in ("awful", "nice"):
        await _put_sense(
            app_client, write_headers,
            sense_id=f"{word}-me-1",
            word=word,
            definition=f"Original meaning of {word}.",
            era_name="Middle English",
            first_attested_year=1300,
            last_attested_year=1500,
            evidence_grade="B",
            semantic_change_type="amelioration",
        )

    resp = await app_client.post(
        "/pg/drift/compare",
        json={"words": ["awful", "nice"], "era": "Middle English"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["era"] == "Middle English"
    compared_words = {c["word"] for c in data["comparison"]}
    assert compared_words == {"awful", "nice"}
    for entry in data["comparison"]:
        assert "vitality_score" in entry
        assert "vitality_status" in entry


async def test_drift_compare_without_era(app_client, write_headers):
    await _put_sense(
        app_client, write_headers,
        sense_id="charity-1",
        word="charity",
        definition="Love for humanity.",
        first_attested_year=1200,
        last_attested_year=1800,
        evidence_grade="A",
    )
    resp = await app_client.post(
        "/pg/drift/compare",
        json={"words": ["charity"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["era"] is None
    assert len(data["comparison"]) == 1


# ---------------------------------------------------------------------------
# Drift trajectory
# ---------------------------------------------------------------------------

async def test_drift_trajectory_ordered_sequence(app_client, write_headers):
    for i, (year, change) in enumerate([
        (1200, "amelioration"),
        (1450, "pejoration"),
        (1700, "bleaching"),
    ]):
        await _put_sense(
            app_client, write_headers,
            sense_id=f"nice-{i}",
            word="nice",
            definition=f"Meaning circa {year}.",
            first_attested_year=year,
            semantic_change_type=change,
            era_name="Middle English" if year < 1470 else "Early Modern English",
        )

    resp = await app_client.get("/pg/word/nice/drift-trajectory")
    assert resp.status_code == 200
    data = resp.json()
    assert data["word"] == "nice"
    assert len(data["trajectory"]) == 3
    assert data["sequence"] == ["amelioration", "pejoration", "bleaching"]
    assert data["unique_change_types"] == 3
    assert data["spans_years"] == 500


async def test_drift_trajectory_not_found(app_client):
    resp = await app_client.get("/pg/word/zzznonsense/drift-trajectory")
    assert resp.status_code == 404
