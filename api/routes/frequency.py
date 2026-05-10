"""Frequency-informed word trend endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_pg_session
from db import crud
from living_lexicon.vitality import compute_vitality

router = APIRouter(prefix="/pg", tags=["frequency"])


class TrendingWord(BaseModel):
    word: str
    wordfreq_zipf: float
    vitality_score: float
    status: str
    sense_count: int
    drift_velocity: float


@router.get("/words/trending", response_model=list[TrendingWord])
async def trending_words(
    direction: str = Query(default="rising", description="rising | declining"),
    min_zipf: float = Query(default=3.0, ge=0.0, le=7.0, description="Minimum Zipf score (0–7)"),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_pg_session),
):
    """
    Return words ranked by vitality, filtered to those with a corpus frequency score.

    - **rising**: high vitality + high frequency → actively used, well-attested vocabulary
    - **declining**: low vitality + high frequency → still in common use but losing scholarly attestation

    Requires wordfreq data to be loaded via `make import-frequency`.
    """
    if direction not in ("rising", "declining"):
        raise HTTPException(status_code=422, detail="direction must be 'rising' or 'declining'")

    word_rows = await crud.list_words_with_frequency(session, min_zipf=min_zipf, limit=limit * 3)
    if not word_rows:
        return []

    results: list[TrendingWord] = []
    for row in word_rows:
        senses = await crud.list_senses(session, row.word)
        breakdown = compute_vitality(senses, zipf=row.wordfreq_zipf)
        results.append(TrendingWord(
            word=row.word,
            wordfreq_zipf=row.wordfreq_zipf,
            vitality_score=breakdown.vitality_score,
            status=breakdown.status,
            sense_count=breakdown.sense_count,
            drift_velocity=breakdown.drift_velocity,
        ))

    if direction == "rising":
        results.sort(key=lambda r: r.vitality_score, reverse=True)
    else:
        results.sort(key=lambda r: r.vitality_score)

    return results[:limit]
