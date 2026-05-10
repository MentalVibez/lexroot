"""Word relation endpoints — semantic, etymological, and family graph queries."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_pg_session
from api.security import require_admin_token
from db import crud

router = APIRouter(prefix="/pg", tags=["relations"])

_VALID_RELATION_TYPES = frozenset({
    "synonym", "antonym", "hypernym", "hyponym",
    "meronym", "holonym", "cognate",
    "derived_from", "root_of", "calque_of", "doublet_of",
})


class RelationResponse(BaseModel):
    id: int
    from_word: str
    to_word: str
    relation_type: str
    era_name: str | None = None
    source_slug: str | None = None
    confidence: str

    model_config = {"from_attributes": True}


class RelationPayload(BaseModel):
    from_word: str
    to_word: str
    relation_type: str
    era_name: str | None = None
    source_slug: str | None = None
    confidence: str = "medium"
    notes: str | None = None


class WordFamilyResponse(BaseModel):
    root_word: str
    family: list[str]
    total: int


@router.get("/word/{word}/relations", response_model=list[RelationResponse])
async def get_word_relations(
    word: str,
    type: str | None = Query(default=None, description="Filter by relation type, e.g. synonym, cognate, derived_from"),
    session: AsyncSession = Depends(get_pg_session),
):
    """
    Return all documented relationships from this word to other words.

    Relation types: synonym, antonym, hypernym, hyponym, meronym, holonym,
    cognate, derived_from, root_of, calque_of, doublet_of.
    """
    if type and type not in _VALID_RELATION_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown relation type '{type}'. Valid types: {sorted(_VALID_RELATION_TYPES)}",
        )
    return await crud.get_word_relations(session, word, relation_type=type)


@router.get("/word/{word}/family", response_model=WordFamilyResponse)
async def get_word_family(
    word: str,
    depth: int = Query(default=3, ge=1, le=5),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_pg_session),
):
    """
    Return all words in the same derivational family via derived_from / root_of edges.

    Traversal is BFS up to `depth` hops from the root word. The most useful
    endpoint for vocabulary instruction: find all English words derived from a
    Latin root.
    """
    family = await crud.get_word_family(session, word, depth=depth, limit=limit)
    return WordFamilyResponse(root_word=word, family=family, total=len(family))


@router.post("/word/relation", response_model=RelationResponse, status_code=201)
async def add_word_relation(
    payload: RelationPayload,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_pg_session),
):
    """Add a semantic or etymological relation edge between two words. Admin only."""
    require_admin_token(authorization)
    if payload.relation_type not in _VALID_RELATION_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown relation type '{payload.relation_type}'.",
        )
    return await crud.add_word_relation(
        session,
        from_word=payload.from_word.lower(),
        to_word=payload.to_word.lower(),
        relation_type=payload.relation_type,
        era_name=payload.era_name,
        source_slug=payload.source_slug,
        confidence=payload.confidence,
        notes=payload.notes,
    )
