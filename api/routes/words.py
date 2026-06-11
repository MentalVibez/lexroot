from fastapi import APIRouter, HTTPException, Query

from api.deps import get_historian, require_legacy_sdk
from api.schemas import WordContextResponse
from living_lexicon.exceptions import WordNotFoundError

router = APIRouter(tags=["words"])


@router.get("/word/{word}", response_model=WordContextResponse)
def get_word(word: str):
    require_legacy_sdk()
    try:
        ctx = get_historian().context(word)
        return WordContextResponse(
            name=ctx.word,
            language=ctx.language,
            definition=ctx.definition,
            root=ctx.root.name,
            root_meaning=ctx.root.meaning,
            root_origin=ctx.root.origin_language,
            cognates=ctx.cognates,
        )
    except WordNotFoundError:
        raise HTTPException(status_code=404, detail=f"'{word}' not found in the lexicon")


@router.get("/word/{word}/tree")
def get_word_tree(word: str):
    require_legacy_sdk()
    tree = get_historian()._store.get_word_tree(word)
    if not tree:
        raise HTTPException(status_code=404, detail=f"No root tree found for '{word}'")
    return tree


@router.get("/word/{word}/cognates")
def get_cognates(word: str):
    require_legacy_sdk()
    cognates = get_historian()._store.get_cognates(word)
    if not cognates:
        raise HTTPException(status_code=404, detail=f"No cognates found for '{word}'")
    return {"word": word, "cognates": cognates}


@router.get("/word/{word}/etymology-claims")
def get_etymology_claims(word: str):
    require_legacy_sdk()
    if not get_historian()._store.get_word(word):
        raise HTTPException(status_code=404, detail=f"'{word}' not found in the lexicon")
    claims = get_historian()._store.get_etymology_claims(word)
    return {"word": word, "claims": claims}


@router.get("/word/{word}/retrieval-bundle")
def get_retrieval_bundle(word: str):
    require_legacy_sdk()
    try:
        bundle = get_historian().retrieval_bundle(word)
    except WordNotFoundError:
        raise HTTPException(status_code=404, detail=f"'{word}' not found in the lexicon")

    return {
        "word": bundle.word,
        "context": {
            "word": bundle.context.word,
            "language": bundle.context.language,
            "definition": bundle.context.definition,
            "root": {
                "name": bundle.context.root.name,
                "meaning": bundle.context.root.meaning,
                "origin_language": bundle.context.root.origin_language,
            },
            "cognates": bundle.context.cognates,
        },
        "claims": [
            {
                "id": c.id,
                "relation_type": c.relation_type,
                "source_form": c.source_form,
                "source_language": c.source_language,
                "confidence": c.confidence,
                "score": c.score,
                "source_slug": c.source_slug,
                "source_short_name": c.source_short_name,
                "source_tier": c.source_tier,
                "note": c.note,
                "is_reconstructed": c.is_reconstructed,
            }
            for c in bundle.claims
        ],
        "timeline": [
            {
                "era_name": era.era_name,
                "start_year": era.start_year,
                "end_year": era.end_year,
                "meaning": era.meaning,
                "usage_example": era.usage_example,
                "source": (
                    {
                        "slug": era.source.slug,
                        "short_name": era.source.short_name,
                        "authority_tier": era.source.authority_tier,
                    }
                    if era.source
                    else None
                ),
            }
            for era in bundle.timeline
        ],
        "sources": [
            {
                "slug": s.slug,
                "short_name": s.short_name,
                "authority_tier": s.authority_tier,
                "year": s.year,
                "category": s.category,
            }
            for s in bundle.sources
        ],
        "evidence_summary": bundle.evidence_summary,
    }


@router.get("/word/{word}/word-detective")
def get_word_detective(word: str):
    require_legacy_sdk()
    try:
        result = get_historian().word_detective(word)
    except WordNotFoundError:
        raise HTTPException(status_code=404, detail=f"'{word}' not found in the lexicon")
    return result.__dict__


@router.get("/search")
def search(q: str = Query(..., min_length=2), limit: int = Query(default=10, le=50)):
    require_legacy_sdk()
    results = get_historian()._store.search(q, limit)
    return {"query": q, "results": results}
