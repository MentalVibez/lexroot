"""Tests for the contributor submission and review workflow."""
from __future__ import annotations

import pytest


_SENSE_PAYLOAD = {
    "word": "awful",
    "definition": "Filling one with awe; overwhelming.",
    "era_name": "Old English",
    "part_of_speech": "adjective",
    "confidence": "medium",
    "evidence_grade": "C",
}


async def test_propose_sense_returns_pending(app_client, contributor_headers):
    resp = await app_client.post("/contribute/sense", json=_SENSE_PAYLOAD, headers=contributor_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["review_status"] == "pending"
    assert data["word"] == "awful"
    assert "sense_id" in data


async def test_propose_sense_duplicate_is_409(app_client, contributor_headers):
    await app_client.post("/contribute/sense", json=_SENSE_PAYLOAD, headers=contributor_headers)
    resp = await app_client.post("/contribute/sense", json=_SENSE_PAYLOAD, headers=contributor_headers)
    assert resp.status_code == 409


async def test_propose_attestation_requires_existing_sense(app_client, contributor_headers):
    """Attestation for a non-existent sense must return 404."""
    resp = await app_client.post("/contribute/attestation", json={
        "sense_id": "does-not-exist-xyz",
        "word": "awful",
        "quote": "The awful grandeur of the mountain.",
        "quote_year": 1200,
        "quote_author": "Anonymous",
    }, headers=contributor_headers)
    assert resp.status_code == 404


async def test_propose_attestation_for_existing_sense(app_client, contributor_headers):
    sense_resp = await app_client.post("/contribute/sense", json=_SENSE_PAYLOAD, headers=contributor_headers)
    sense_id = sense_resp.json()["sense_id"]

    resp = await app_client.post("/contribute/attestation", json={
        "sense_id": sense_id,
        "word": "awful",
        "quote": "The awful grandeur of the mountain.",
        "quote_year": 1200,
        "quote_author": "Anonymous",
    }, headers=contributor_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["review_status"] == "pending"


async def test_my_submissions_filters_by_status(app_client, contributor_headers):
    await app_client.post("/contribute/sense", json=_SENSE_PAYLOAD, headers=contributor_headers)

    resp = await app_client.get("/contribute/my-submissions?status=pending", headers=contributor_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["count"] >= 1


async def test_contribute_requires_token(app_client):
    resp = await app_client.post("/contribute/sense", json=_SENSE_PAYLOAD)
    assert resp.status_code in (401, 503)
