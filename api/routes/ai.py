import logging

from fastapi import APIRouter, HTTPException, Query

from api.deps import get_historian, require_legacy_sdk
from api.schemas import DriftResponse, FactCheckPayload, FactCheckResponse, TeachingCardResponse
from living_lexicon.exceptions import LLMError, WordNotFoundError

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ai"])


@router.get("/word/{word}/drift", response_model=DriftResponse)
def semantic_drift(
    word: str,
    context: str | None = Query(default=None, description="biblical | legal | medical | literary"),
):
    require_legacy_sdk()
    try:
        drift = get_historian().explain(word, context=context)
        return DriftResponse(
            word=drift.word,
            context=drift.context_hint,
            root=drift.root.name,
            root_meaning=drift.root.meaning,
            explanation=drift.ai_explanation,
        )
    except WordNotFoundError:
        raise HTTPException(status_code=404, detail=f"'{word}' not found in the lexicon")
    except LLMError as e:
        logger.error("LLM error for word=%r: %s", word, e)
        raise HTTPException(status_code=501, detail="The language model is unavailable")


@router.get("/word/{word}/teaching-card", response_model=TeachingCardResponse)
def get_teaching_card(
    word: str,
    level: str = Query(default="high_school", pattern="^(middle_school|high_school|college|scholarly)$"),
):
    require_legacy_sdk()
    try:
        card = get_historian().teaching_card(word, level=level)
    except WordNotFoundError:
        raise HTTPException(status_code=404, detail=f"'{word}' not found in the lexicon")
    return TeachingCardResponse(**card.__dict__)


@router.post("/word/{word}/fact-check", response_model=FactCheckResponse)
def fact_check_word_answer(word: str, payload: FactCheckPayload):
    require_legacy_sdk()
    try:
        result = get_historian().fact_check_answer(word, payload.answer, strict=payload.strict)
    except WordNotFoundError:
        raise HTTPException(status_code=404, detail=f"'{word}' not found in the lexicon")
    return FactCheckResponse(**result.__dict__)
