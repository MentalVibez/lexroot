"""Contributor submission endpoints — propose senses without admin access."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_pg_session
from api.security import require_contributor_token
from db import crud

router = APIRouter(prefix="/contribute", tags=["contributions"])


def _contributor_id(token: str, word: str) -> str:
    """Opaque traceable ID — never stores the raw token."""
    return hashlib.sha256(f"{token}:{word}".encode()).hexdigest()[:16]


def _generate_sense_id(word: str, era_name: str | None, definition: str) -> str:
    """Server-generated sense_id so contributors cannot overwrite curated senses."""
    era = (era_name or "undated").lower().replace(" ", "-")
    defn_hash = hashlib.sha1(definition.encode()).hexdigest()[:8]
    return f"{word.lower()}-{era}-contrib-{defn_hash}"


class ContributeSenseRequest(BaseModel):
    word: str = Field(min_length=1, max_length=255)
    definition: str = Field(min_length=1)
    era_name: str | None = None
    part_of_speech: str | None = Field(default=None, max_length=80)
    meaning_type: str = Field(default="attested", max_length=80)
    domain: str | None = Field(default=None, max_length=120)
    first_attested_year: int | None = None
    last_attested_year: int | None = None
    source_slug: str | None = Field(default=None, max_length=120)
    confidence: str = Field(default="low", max_length=40)
    confidence_reason: str | None = None
    evidence_grade: str | None = Field(default=None, max_length=1)
    citation: str | None = None
    source_url: str | None = None
    semantic_change_type: str | None = Field(default=None, max_length=80)
    notes: str | None = None


class ContributeAttestationRequest(BaseModel):
    sense_id: str = Field(min_length=1, max_length=255)
    word: str = Field(min_length=1, max_length=255)
    quote: str | None = None
    quote_year: int | None = None
    quote_author: str | None = None
    quote_work: str | None = None
    source_slug: str | None = Field(default=None, max_length=120)
    evidence_grade: str | None = Field(default=None, max_length=1)
    citation: str | None = None
    notes: str | None = None


class SubmissionResponse(BaseModel):
    sense_id: str
    word: str
    review_status: str
    message: str


@router.post("/sense", response_model=SubmissionResponse, status_code=201)
async def propose_sense(
    payload: ContributeSenseRequest,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_pg_session),
):
    """
    Propose a new sense for review. No admin token required — contributor token only.

    The sense is created with review_status='pending' and will not appear in
    public search results until approved by an admin via PATCH /admin/review/sense/{id}.
    """
    token = require_contributor_token(authorization)
    sense_id = _generate_sense_id(payload.word, payload.era_name, payload.definition)
    contributor_id = _contributor_id(token, payload.word)

    existing = await crud.get_sense(session, sense_id)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"An identical sense already exists (ID: {sense_id}). "
                   "If this is a different meaning, adjust the definition wording.",
        )

    await crud.upsert_sense(
        session,
        sense_id=sense_id,
        word=payload.word.lower(),
        definition=payload.definition,
        part_of_speech=payload.part_of_speech,
        meaning_type=payload.meaning_type,
        domain=payload.domain,
        era_name=payload.era_name,
        first_attested_year=payload.first_attested_year,
        last_attested_year=payload.last_attested_year,
        source_slug=payload.source_slug,
        confidence=payload.confidence,
        confidence_reason=payload.confidence_reason,
        evidence_grade=payload.evidence_grade,
        citation=payload.citation,
        source_url=payload.source_url,
        semantic_change_type=payload.semantic_change_type,
        notes=payload.notes,
        review_status="pending",
        submitted_by=contributor_id,
        submitted_at=datetime.now(timezone.utc),
    )

    return SubmissionResponse(
        sense_id=sense_id,
        word=payload.word,
        review_status="pending",
        message="Sense submitted for review. Track status via GET /contribute/my-submissions.",
    )


@router.post("/attestation", status_code=201)
async def propose_attestation(
    payload: ContributeAttestationRequest,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_pg_session),
):
    """Propose an attestation (quotation evidence) for an existing sense."""
    token = require_contributor_token(authorization)
    contributor_id = _contributor_id(token, payload.word)

    sense = await crud.get_sense(session, payload.sense_id)
    if sense is None:
        raise HTTPException(status_code=404, detail=f"Sense '{payload.sense_id}' not found.")

    att = await crud.add_attestation(
        session,
        sense_id=payload.sense_id,
        word=payload.word.lower(),
        quote=payload.quote,
        quote_year=payload.quote_year,
        quote_author=payload.quote_author,
        quote_work=payload.quote_work,
        source_slug=payload.source_slug,
        attestation_type="quotation",
        evidence_grade=payload.evidence_grade,
        citation=payload.citation,
        notes=payload.notes,
        review_status="pending",
    )
    return {"attestation_id": att.id, "review_status": "pending", "message": "Attestation submitted for review."}


@router.get("/my-submissions")
async def my_submissions(
    status: str = Query(default="pending", description="pending | approved | rejected"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_pg_session),
):
    """List your own submitted senses, filtered by review status."""
    token = require_contributor_token(authorization)

    if status not in ("pending", "approved", "rejected"):
        raise HTTPException(status_code=422, detail="status must be pending, approved, or rejected")

    # We can't filter by contributor_id without knowing the word, so we return
    # all senses with matching review_status — a contributor sees approved ones too.
    # For production, index submitted_by and filter on it.
    senses = await crud.list_senses_by_review_status(
        session, review_status=status, offset=offset, limit=limit
    )
    return {
        "status": status,
        "count": len(senses),
        "senses": [
            {"sense_id": s.sense_id, "word": s.word, "definition": s.definition,
             "era_name": s.era_name, "review_status": s.review_status}
            for s in senses
        ],
    }
