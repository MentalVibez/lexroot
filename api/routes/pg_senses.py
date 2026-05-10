from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_pg_session
from api.security import require_admin_token
from db import crud

router = APIRouter(prefix="/pg", tags=["senses-pg"])


class SenseResponse(BaseModel):
    id: int
    sense_id: str
    word: str
    entry_type: str
    part_of_speech: str | None = None
    definition: str
    meaning_type: str
    lexical_register: str | None = Field(
        default=None,
        validation_alias="register",
        serialization_alias="register",
    )
    domain: str | None = None
    era_name: str | None = None
    first_attested_year: int | None = None
    last_attested_year: int | None = None
    first_attested_source: str | None = None
    source_slug: str | None = None
    confidence: str
    confidence_reason: str | None = None
    evidence_grade: str | None = None
    citation: str | None = None
    page: str | None = None
    entry_headword: str | None = None
    source_url: str | None = None
    access_date: str | None = None
    review_status: str | None = None
    semantic_change_type: str | None = None
    origin_status: str | None = None
    usage_region: str | None = None
    usage_register: str | None = None
    notes: str | None = None
    reconstruction_level: str | None = None
    learner_level: str | None = None

    model_config = {"from_attributes": True}


class SensePayload(BaseModel):
    sense_id: str = Field(min_length=1, max_length=255)
    word: str = Field(min_length=1, max_length=255)
    definition: str = Field(min_length=1)
    entry_type: str = Field(default="word", max_length=40)
    part_of_speech: str | None = Field(default=None, max_length=80)
    meaning_type: str = Field(default="attested", max_length=80)
    lexical_register: str | None = Field(
        default=None,
        max_length=80,
        validation_alias="register",
        serialization_alias="register",
    )
    domain: str | None = Field(default=None, max_length=120)
    era_name: str | None = Field(default=None, max_length=120)
    first_attested_year: int | None = None
    last_attested_year: int | None = None
    first_attested_source: str | None = None
    source_slug: str | None = Field(default=None, max_length=120)
    confidence: str = Field(default="medium", max_length=40)
    confidence_reason: str | None = None
    evidence_grade: str | None = Field(default=None, max_length=1)
    citation: str | None = None
    page: str | None = Field(default=None, max_length=80)
    entry_headword: str | None = Field(default=None, max_length=255)
    source_url: str | None = None
    access_date: str | None = Field(default=None, max_length=40)
    review_status: str | None = Field(default=None, max_length=40)
    semantic_change_type: str | None = Field(default=None, max_length=80)
    origin_status: str | None = Field(default=None, max_length=80)
    usage_region: str | None = Field(default=None, max_length=120)
    usage_register: str | None = Field(default=None, max_length=80)
    notes: str | None = None


class AttestationResponse(BaseModel):
    id: int
    sense_id: str
    word: str
    quote: str | None = None
    quote_year: int | None = None
    quote_author: str | None = None
    quote_work: str | None = None
    source_slug: str | None = None
    attestation_type: str
    citation: str | None = None
    evidence_grade: str | None = None
    confidence_reason: str | None = None
    page: str | None = None
    entry_headword: str | None = None
    source_url: str | None = None
    access_date: str | None = None
    review_status: str | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}


class AttestationPayload(BaseModel):
    sense_id: str = Field(min_length=1, max_length=255)
    word: str = Field(min_length=1, max_length=255)
    quote: str | None = None
    quote_year: int | None = None
    quote_author: str | None = Field(default=None, max_length=255)
    quote_work: str | None = Field(default=None, max_length=255)
    source_slug: str | None = Field(default=None, max_length=120)
    attestation_type: str = Field(default="historical_dictionary", max_length=80)
    citation: str | None = None
    evidence_grade: str | None = Field(default=None, max_length=1)
    confidence_reason: str | None = None
    page: str | None = Field(default=None, max_length=80)
    entry_headword: str | None = Field(default=None, max_length=255)
    source_url: str | None = None
    access_date: str | None = Field(default=None, max_length=40)
    review_status: str | None = Field(default=None, max_length=40)
    notes: str | None = None


@router.get("/word/{word}/senses", response_model=list[SenseResponse])
async def get_word_senses(
    word: str,
    learner_level: str | None = Query(default=None, description="beginner | intermediate | advanced | research"),
    reconstruction_level: str | None = Query(default=None, description="attested | reconstructed | disputed | folk_etymology"),
    session: AsyncSession = Depends(get_pg_session),
):
    senses = await crud.list_senses(session, word)
    if learner_level:
        senses = [s for s in senses if getattr(s, "learner_level", None) == learner_level]
    if reconstruction_level:
        senses = [s for s in senses if getattr(s, "reconstruction_level", None) == reconstruction_level]
    return senses


@router.get("/sense/{sense_id}", response_model=SenseResponse)
async def get_sense(sense_id: str, session: AsyncSession = Depends(get_pg_session)):
    row = await crud.get_sense(session, sense_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Sense '{sense_id}' not found")
    return row


@router.put("/sense", response_model=SenseResponse)
async def upsert_sense(
    payload: SensePayload,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_pg_session),
):
    require_admin_token(authorization)
    return await crud.upsert_sense(session, **payload.model_dump(by_alias=True))


@router.get("/sense/{sense_id}/attestations", response_model=list[AttestationResponse])
async def get_sense_attestations(sense_id: str, session: AsyncSession = Depends(get_pg_session)):
    return await crud.list_attestations(session, sense_id)


@router.post("/attestation", response_model=AttestationResponse)
async def add_attestation(
    payload: AttestationPayload,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_pg_session),
):
    require_admin_token(authorization)
    return await crud.add_attestation(session, **payload.model_dump())
