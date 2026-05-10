"""Semantic field queries, comparative drift, and drift trajectory endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_pg_session
from db import crud
from living_lexicon.vitality import compute_vitality

router = APIRouter(prefix="/pg", tags=["semantic-fields"])


# ---------------------------------------------------------------------------
# Semantic field clustering
# ---------------------------------------------------------------------------

class FieldSense(BaseModel):
    word: str
    sense_id: str
    definition: str
    era_name: str | None
    first_attested_year: int | None
    evidence_grade: str | None
    semantic_change_type: str | None
    part_of_speech: str | None
    source_slug: str | None


class SemanticFieldResponse(BaseModel):
    filters: dict
    total: int
    senses: list[FieldSense]


@router.get("/semantic-fields", response_model=SemanticFieldResponse)
async def semantic_field_query(
    domain: str | None = Query(default=None, description="e.g. 'law', 'medicine', 'theology'"),
    change_type: str | None = Query(default=None, description="e.g. 'pejoration', 'amelioration', 'bleaching'"),
    era: str | None = Query(default=None, description="Canonical era name, e.g. 'Middle English'"),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_pg_session),
):
    """
    Find senses that share a domain, semantic change type, and/or era.
    All parameters are optional and composable.

    Useful for linguistic field research: e.g. all words that underwent
    pejoration in legal contexts during Early Modern English.
    """
    if not any([domain, change_type, era]):
        raise HTTPException(
            status_code=422,
            detail="At least one filter (domain, change_type, or era) is required."
        )

    senses = await crud.list_senses_by_field(
        session,
        domain=domain,
        semantic_change_type=change_type,
        era_name=era,
        limit=limit,
    )

    return SemanticFieldResponse(
        filters={k: v for k, v in {"domain": domain, "change_type": change_type, "era": era}.items() if v},
        total=len(senses),
        senses=[
            FieldSense(
                word=s.word,
                sense_id=s.sense_id,
                definition=s.definition,
                era_name=s.era_name,
                first_attested_year=s.first_attested_year,
                evidence_grade=s.evidence_grade,
                semantic_change_type=s.semantic_change_type,
                part_of_speech=s.part_of_speech,
                source_slug=s.source_slug,
            )
            for s in senses
        ],
    )


# ---------------------------------------------------------------------------
# Comparative drift
# ---------------------------------------------------------------------------

class CompareRequest(BaseModel):
    words: list[str] = Field(min_length=1, max_length=20)
    era: str | None = None


class WordComparison(BaseModel):
    word: str
    senses_in_era: int
    best_evidence_grade: str | None
    semantic_change_types: list[str]
    definition_excerpt: str | None
    vitality_score: float
    vitality_status: str


class ComparisonResponse(BaseModel):
    era: str | None
    comparison: list[WordComparison]


@router.post("/drift/compare", response_model=ComparisonResponse)
async def compare_drift(
    payload: CompareRequest,
    session: AsyncSession = Depends(get_pg_session),
):
    """
    Compare how multiple words behaved in the same era.

    Returns evidence-graded era senses + vitality scores for each word,
    in a single response — the core operation for comparative historical semantics.
    """
    words = [w.lower().strip() for w in payload.words]

    if payload.era:
        era_map = await crud.bulk_get_senses_by_era(session, words, payload.era)
    else:
        era_map = {w: [] for w in words}

    comparison: list[WordComparison] = []
    for word in words:
        all_senses = await crud.list_senses(session, word)
        era_senses = era_map.get(word, [])
        breakdown = compute_vitality(all_senses)

        grades = sorted(
            {s.evidence_grade for s in era_senses if s.evidence_grade},
            key=lambda g: ord(g)
        )
        change_types = sorted({
            s.semantic_change_type for s in era_senses
            if s.semantic_change_type and s.semantic_change_type != "unknown"
        })
        best_def = era_senses[0].definition if era_senses else None

        comparison.append(WordComparison(
            word=word,
            senses_in_era=len(era_senses),
            best_evidence_grade=grades[0] if grades else None,
            semantic_change_types=change_types,
            definition_excerpt=(best_def[:150] + "…" if best_def and len(best_def) > 150 else best_def),
            vitality_score=breakdown.vitality_score,
            vitality_status=breakdown.status,
        ))

    return ComparisonResponse(era=payload.era, comparison=comparison)


# ---------------------------------------------------------------------------
# Drift trajectory  (also lives here but exposed under /pg/word/{word}/)
# ---------------------------------------------------------------------------

class TrajectoryEra(BaseModel):
    era: str | None
    change_type: str | None
    definition_excerpt: str | None
    evidence_grade: str | None
    first_attested_year: int | None


class DriftTrajectoryResponse(BaseModel):
    word: str
    trajectory: list[TrajectoryEra]
    sequence: list[str]
    unique_change_types: int
    spans_years: int | None


@router.get("/word/{word}/drift-trajectory", response_model=DriftTrajectoryResponse)
async def drift_trajectory(
    word: str,
    session: AsyncSession = Depends(get_pg_session),
):
    """
    Return the ordered sequence of semantic changes across a word's attested history.

    The `sequence` field is the named drift pathway — e.g. ["amelioration", "pejoration"]
    for "nice". Useful for identifying chain shifts and semantic bleaching patterns.
    """
    senses = await crud.list_senses(session, word)
    if not senses:
        raise HTTPException(status_code=404, detail=f"No senses found for '{word}'")

    trajectory: list[TrajectoryEra] = []
    seen_change: list[str] = []

    for s in senses:
        defn = s.definition or ""
        trajectory.append(TrajectoryEra(
            era=s.era_name,
            change_type=s.semantic_change_type,
            definition_excerpt=defn[:120] + "…" if len(defn) > 120 else defn,
            evidence_grade=s.evidence_grade,
            first_attested_year=s.first_attested_year,
        ))
        if s.semantic_change_type and s.semantic_change_type != "unknown":
            if not seen_change or seen_change[-1] != s.semantic_change_type:
                seen_change.append(s.semantic_change_type)

    years = [s.first_attested_year for s in senses if s.first_attested_year]
    spans = (max(years) - min(years)) if len(years) >= 2 else None

    return DriftTrajectoryResponse(
        word=word,
        trajectory=trajectory,
        sequence=seen_change,
        unique_change_types=len(set(seen_change)),
        spans_years=spans,
    )
