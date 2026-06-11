from fastapi import APIRouter, HTTPException, Query

from api.deps import get_historian, require_legacy_sdk

router = APIRouter(tags=["sources"])


@router.get("/sources")
def list_sources(limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    require_legacy_sdk()
    all_sources = get_historian()._store.get_all_sources()
    return {"sources": all_sources[offset : offset + limit], "total": len(all_sources)}


@router.get("/sources/{slug}")
def get_source(slug: str):
    require_legacy_sdk()
    source = get_historian()._store.get_source(slug)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source '{slug}' not found")
    return source


@router.get("/word/{word}/sources")
def get_word_sources(word: str):
    require_legacy_sdk()
    if not get_historian()._store.get_word(word):
        raise HTTPException(status_code=404, detail=f"'{word}' not found in the lexicon")
    return {"word": word, "sources": get_historian()._store.get_word_sources(word)}


@router.get("/sources/{slug}/words")
def get_words_by_source(
    slug: str,
    limit: int = Query(default=20, ge=1, le=100),
):
    require_legacy_sdk()
    if not get_historian()._store.get_source(slug):
        raise HTTPException(status_code=404, detail=f"Source '{slug}' not found")
    return {"source": slug, "words": get_historian()._store.get_words_by_source(slug, limit)}
