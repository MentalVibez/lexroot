from fastapi import APIRouter, HTTPException, Query

from api.deps import get_historian, require_legacy_sdk
from living_lexicon.exceptions import LLMError, WordNotFoundError


router = APIRouter(tags=["eras"])


@router.get("/word/{word}/era-timeline")
def get_era_timeline(word: str):
    require_legacy_sdk()
    try:
        records = get_historian().timeline(word)
        return {
            "word": word,
            "timeline": [
                {
                    "era_name": r.era_name,
                    "era_start": r.start_year,
                    "era_end": r.end_year,
                    "meaning": r.meaning,
                    "usage_example": r.usage_example,
                }
                for r in records
            ],
        }
    except WordNotFoundError:
        raise HTTPException(status_code=404, detail=f"'{word}' not found in the lexicon")


@router.get("/word/{word}/era/{era_name:path}")
def get_word_in_era(
    word: str,
    era_name: str,
    snippet: str | None = Query(default=None),
):
    require_legacy_sdk()
    try:
        era_ctx = get_historian().in_era(word, era_name, snippet=snippet)
        return {
            "word": era_ctx.word,
            "era": era_ctx.era_name,
            "historical_meaning": era_ctx.historical_meaning,
            "usage_example": era_ctx.usage_example,
            "modern_definition": era_ctx.modern_definition,
            "ai_explanation": era_ctx.ai_explanation,
        }
    except WordNotFoundError:
        raise HTTPException(status_code=404, detail=f"'{word}' not found in the lexicon")
    except LLMError as e:
        raise HTTPException(status_code=501, detail=str(e))


@router.get("/era/by-year/{year}")
def get_era_by_year(year: int):
    require_legacy_sdk()
    era = get_historian()._store.get_era_by_year(year)
    if not era:
        raise HTTPException(status_code=404, detail=f"No era found for year {year}")
    return era


@router.get("/era/{era_name:path}/words")
def get_era_words(
    era_name: str,
    limit: int = Query(default=20, le=100),
):
    require_legacy_sdk()
    canonical = era_name.replace("-", " ").title()
    words = get_historian()._store.get_words_by_era(canonical, limit)
    return {"era": canonical, "words": words}
