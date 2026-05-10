"""Citation export endpoints — BibTeX, APA, MLA, Chicago."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_pg_session
from db import crud
from living_lexicon.citation_formatter import to_apa, to_bibtex, to_chicago, to_mla, word_to_bibtex

router = APIRouter(prefix="/pg", tags=["citations"])

_FORMATS = {"bibtex", "apa", "mla", "chicago"}


class CitationResponse(BaseModel):
    format: str
    citation_key: str | None
    raw: str


def _cite(sense, fmt: str, access_url: str | None) -> CitationResponse:
    from living_lexicon.citation_formatter import _citation_key
    key = _citation_key(sense) if fmt == "bibtex" else None
    fn = {"bibtex": to_bibtex, "apa": to_apa, "mla": to_mla, "chicago": to_chicago}[fmt]
    return CitationResponse(format=fmt, citation_key=key, raw=fn(sense, access_url=access_url))


@router.get("/sense/{sense_id}/cite", response_model=CitationResponse)
async def cite_sense(
    sense_id: str,
    format: str = Query(default="bibtex", description="bibtex | apa | mla | chicago"),
    base_url: str = Query(default="", description="Optional base URL for sense links"),
    session: AsyncSession = Depends(get_pg_session),
):
    """Return an academic citation for a single sense."""
    if format not in _FORMATS:
        raise HTTPException(status_code=422, detail=f"format must be one of: {', '.join(sorted(_FORMATS))}")
    sense = await crud.get_sense(session, sense_id)
    if sense is None:
        raise HTTPException(status_code=404, detail=f"Sense '{sense_id}' not found")
    access_url = f"{base_url.rstrip('/')}/pg/sense/{sense_id}" if base_url else None
    return _cite(sense, format, access_url)


@router.get("/word/{word}/cite", response_model=CitationResponse)
async def cite_word(
    word: str,
    format: str = Query(default="bibtex", description="bibtex | apa | mla | chicago"),
    base_url: str = Query(default="", description="Optional base URL for sense links"),
    session: AsyncSession = Depends(get_pg_session),
):
    """Return a citation block for all senses of a word (multi-entry BibTeX, or numbered list)."""
    if format not in _FORMATS:
        raise HTTPException(status_code=422, detail=f"format must be one of: {', '.join(sorted(_FORMATS))}")
    senses = await crud.list_senses(session, word)
    if not senses:
        raise HTTPException(status_code=404, detail=f"No senses found for '{word}'")

    access_base = f"{base_url.rstrip('/')}" if base_url else None

    if format == "bibtex":
        raw = word_to_bibtex(senses, access_base_url=f"{access_base}/pg/sense" if access_base else None)
        return CitationResponse(format="bibtex", citation_key=None, raw=raw)

    fn = {"apa": to_apa, "mla": to_mla, "chicago": to_chicago}[format]
    ordered = sorted(senses, key=lambda s: s.first_attested_year or 0)
    lines = []
    for i, sense in enumerate(ordered, 1):
        url = f"{access_base}/pg/sense/{sense.sense_id}" if access_base else None
        lines.append(f"[{i}] {fn(sense, access_url=url)}")
    return CitationResponse(format=format, citation_key=None, raw="\n\n".join(lines))
