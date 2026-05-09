from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_pg_session
from api.schemas import PaginatedResponse
from api.security import require_admin_token
from db import crud

router = APIRouter(prefix="/pg", tags=["words-pg"])


class WordResponse(BaseModel):
    id: int
    word: str
    phonemes: str | None = None
    etymology_root: str | None = None
    definition: str | None = None
    origin_language: str | None = None
    language_family: str | None = None
    historical_context: str | None = None
    semantic_drift_history: list | None = None

    model_config = {"from_attributes": True}


class WordUpsertPayload(BaseModel):
    word: str = Field(min_length=1, max_length=255)
    phonemes: str | None = None
    etymology_root: str | None = None
    definition: str | None = None
    origin_language: str | None = Field(default=None, max_length=100)
    language_family: str | None = Field(default=None, max_length=100)
    historical_context: str | None = None
    semantic_drift_history: list | None = None


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
        phonemes=payload.phonemes,
        etymology_root=payload.etymology_root,
        definition=payload.definition,
        origin_language=payload.origin_language,
        language_family=payload.language_family,
        historical_context=payload.historical_context,
        semantic_drift_history=payload.semantic_drift_history,
    )
