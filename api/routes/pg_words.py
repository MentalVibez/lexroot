from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_pg_session
from api.schemas import PaginatedResponse
from api.security import require_admin_token
from db import crud
from living_lexicon.etymology_path import build_etymology_path
from living_lexicon.vitality import compute_vitality

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z'-]*[a-zA-Z]|[a-zA-Z]")

router = APIRouter(prefix="/pg", tags=["words-pg"])


class WordResponse(BaseModel):
    id: int
    word: str
    entry_type: str = "word"
    phonemes: str | None = None
    etymology_root: str | None = None
    definition: str | None = None
    definition_source_slug: str | None = None
    definition_source_name: str | None = None
    definition_license: str | None = None
    origin_language: str | None = None
    language_family: str | None = None
    historical_context: str | None = None
    literal_meaning: str | None = None
    figurative_meaning: str | None = None
    example_usage: str | None = None
    semantic_drift_history: list | None = None

    model_config = {"from_attributes": True}


class WordUpsertPayload(BaseModel):
    word: str = Field(min_length=1, max_length=255)
    entry_type: str = Field(default="word", max_length=40)
    phonemes: str | None = None
    etymology_root: str | None = None
    definition: str | None = None
    definition_source_slug: str | None = Field(default=None, max_length=120)
    definition_source_name: str | None = None
    definition_license: str | None = Field(default=None, max_length=80)
    origin_language: str | None = Field(default=None, max_length=100)
    language_family: str | None = Field(default=None, max_length=100)
    historical_context: str | None = None
    literal_meaning: str | None = None
    figurative_meaning: str | None = None
    example_usage: str | None = None
    semantic_drift_history: list | None = None


class VitalityResponse(BaseModel):
    word: str
    vitality_score: float
    metrics: dict
    frequency_zipf: float | None = None
    note: str | None = None


class EraCheckRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    era_name: str = Field(min_length=1, max_length=80)


class FlaggedWord(BaseModel):
    word: str
    era_definition: str
    era_source: str | None
    modern_definition: str | None
    part_of_speech: str | None


class EraCheckResponse(BaseModel):
    era_name: str
    words_checked: int
    flagged_count: int
    flagged: list[FlaggedWord]


@router.post("/word/era-check", response_model=EraCheckResponse)
async def era_check(
    payload: EraCheckRequest,
    session: AsyncSession = Depends(get_pg_session),
):
    """
    Scan a block of text for words whose meaning in a given era differs from
    their modern definition. Useful for period-accuracy checking in writing.

    Returns only words that have a documented sense for the requested era —
    words absent from the lexicon are silently skipped.
    """
    tokens = list({t.lower() for t in _TOKEN_RE.findall(payload.text)})
    if not tokens:
        raise HTTPException(status_code=422, detail="No word tokens found in text.")

    era_senses = await crud.bulk_get_senses_by_era(session, tokens, payload.era_name)
    word_rows = await crud.bulk_get_words(session, [w for w, s in era_senses.items() if s])

    flagged: list[FlaggedWord] = []
    for word, senses in era_senses.items():
        if not senses:
            continue
        best = senses[0]
        modern_def = word_rows[word].definition if word in word_rows else None
        flagged.append(FlaggedWord(
            word=word,
            era_definition=best.definition,
            era_source=best.source_slug,
            modern_definition=modern_def,
            part_of_speech=best.part_of_speech,
        ))

    flagged.sort(key=lambda f: f.word)
    return EraCheckResponse(
        era_name=payload.era_name,
        words_checked=len(tokens),
        flagged_count=len(flagged),
        flagged=flagged,
    )


@router.get("/word/{word}/vitality", response_model=VitalityResponse)
async def get_word_vitality(word: str, session: AsyncSession = Depends(get_pg_session)):
    row = await crud.get_word(session, word)
    if row is None:
        raise HTTPException(status_code=404, detail=f"'{word}' not found in the words table")
    senses = await crud.list_senses(session, word)
    breakdown = compute_vitality(senses, zipf=row.wordfreq_zipf if hasattr(row, "wordfreq_zipf") else None)
    note = None
    if breakdown.drift_velocity >= 0.4:
        change_types = sorted({
            s.semantic_change_type for s in senses
            if s.semantic_change_type and s.semantic_change_type != "unknown"
        })
        if change_types:
            note = f"Semantic shifts detected: {', '.join(change_types)}."
    return VitalityResponse(
        word=word,
        vitality_score=breakdown.vitality_score,
        frequency_zipf=breakdown.frequency_zipf,
        metrics={
            "stability": breakdown.stability,
            "drift_velocity": breakdown.drift_velocity,
            "attestation_recency": breakdown.attestation_recency,
            "last_attested": breakdown.last_attested_year,
            "sense_count": breakdown.sense_count,
            "status": breakdown.status,
        },
        note=note,
    )


class EtymologyStepResponse(BaseModel):
    form: str
    language: str
    era_or_period: str | None
    meaning: str | None
    reconstruction_level: str


class EtymologyPathResponse(BaseModel):
    word: str
    steps: list[EtymologyStepResponse]
    origin_language: str | None
    language_family: str | None
    total_steps: int


@router.get("/word/{word}/etymology-path", response_model=EtymologyPathResponse)
async def get_etymology_path(word: str, session: AsyncSession = Depends(get_pg_session)):
    """
    Return the ordered etymology path for a word — from proto-language ancestors
    through each historical era to the modern form.

    Each step shows the form, the language, the era, and the meaning at that stage.
    Steps are ordered oldest to newest, making this the core endpoint for
    classroom etymology instruction.
    """
    row = await crud.get_word(session, word)
    if row is None:
        raise HTTPException(status_code=404, detail=f"'{word}' not found in the words table")
    senses = await crud.list_senses(session, word)
    relations = await crud.get_word_relations(session, word, relation_type="derived_from")
    path = build_etymology_path(row, senses, relations)
    return EtymologyPathResponse(
        word=path.word,
        steps=[EtymologyStepResponse(**vars(s)) for s in path.steps],
        origin_language=path.origin_language,
        language_family=path.language_family,
        total_steps=path.total_steps,
    )


@router.get("/word/{word}", response_model=WordResponse)
async def get_word(word: str, session: AsyncSession = Depends(get_pg_session)):
    row = await crud.get_word(session, word)
    if row is None:
        raise HTTPException(status_code=404, detail=f"'{word}' not found in the words table")
    return row


@router.get("/words", response_model=PaginatedResponse[WordResponse])
async def list_words(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_pg_session),
):
    items = await crud.list_words(session, offset=offset, limit=limit)
    total = await crud.count_words(session)
    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/words/search", response_model=list[WordResponse])
async def search_words(
    q: str = Query(min_length=1, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_pg_session),
):
    return await crud.search_words(session, prefix=q, limit=limit)


class MorphemeResponse(BaseModel):
    id: int
    word: str
    morpheme: str
    role: str
    origin_language: str | None = None
    gloss: str | None = None
    position: int | None = None
    source_slug: str | None = None

    model_config = {"from_attributes": True}


@router.get("/word/{word}/morphemes", response_model=list[MorphemeResponse])
async def get_word_morphemes(word: str, session: AsyncSession = Depends(get_pg_session)):
    """Return the morphological decomposition (prefix/root/suffix) for a word."""
    return await crud.get_morphemes(session, word)


@router.get("/morpheme/{morpheme}/words", response_model=list[str])
async def find_words_by_morpheme(
    morpheme: str,
    role: str | None = Query(default=None, description="prefix | root | suffix | infix"),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_pg_session),
):
    """Find all words that contain a given morpheme (e.g. all words with Latin root 'port')."""
    return await crud.find_words_by_morpheme(session, morpheme=morpheme, role=role, limit=limit)


@router.put("/word", response_model=WordResponse)
async def upsert_word(
    payload: WordUpsertPayload,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_pg_session),
):
    require_admin_token(authorization)
    return await crud.upsert_word(
        session,
        word=payload.word,
        entry_type=payload.entry_type,
        phonemes=payload.phonemes,
        etymology_root=payload.etymology_root,
        definition=payload.definition,
        definition_source_slug=payload.definition_source_slug,
        definition_source_name=payload.definition_source_name,
        definition_license=payload.definition_license,
        origin_language=payload.origin_language,
        language_family=payload.language_family,
        historical_context=payload.historical_context,
        literal_meaning=payload.literal_meaning,
        figurative_meaning=payload.figurative_meaning,
        example_usage=payload.example_usage,
        semantic_drift_history=payload.semantic_drift_history,
    )
