from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard pagination envelope used by all list endpoints."""
    items: list[T]
    total: int
    offset: int
    limit: int


# ---------------------------------------------------------------------------
# Request payloads
# ---------------------------------------------------------------------------

class IngestPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    language: str = Field(default="English", max_length=80)
    definition: str = Field(min_length=1, max_length=5000)
    root_name: str = Field(min_length=1, max_length=120)
    root_meaning: str = Field(min_length=1, max_length=2000)
    root_origin_language: str = Field(default="Proto-Indo-European", max_length=120)
    cognates: list[str] = Field(default_factory=list)


class FactCheckPayload(BaseModel):
    answer: str = Field(min_length=1, max_length=12000)
    strict: bool = True


# ---------------------------------------------------------------------------
# Response models — stable contract for downstream consumers
# ---------------------------------------------------------------------------

class WordContextResponse(BaseModel):
    name: str
    language: str
    definition: str
    root: str
    root_meaning: str
    root_origin: str
    cognates: list[str]


class EtymologyClaimResponse(BaseModel):
    id: str
    relation_type: str
    source_form: str
    source_language: str
    confidence: str
    score: float
    source_slug: str | None = None
    source_short_name: str | None = None
    source_tier: int = 99
    note: str | None = None
    is_reconstructed: bool = False


class DriftResponse(BaseModel):
    word: str
    context: str | None
    root: str
    root_meaning: str
    explanation: str


class TeachingCardResponse(BaseModel):
    word: str
    level: str
    modern_definition: str
    best_origin: str
    then_vs_now: dict
    misconception_check: str
    classroom_example: dict
    discussion_questions: list[str]
    activity: dict
    curriculum_tags: list[str]
    content_warnings: list[str]
    evidence_label: str
    religious_text_note: str | None = None


class FactCheckResponse(BaseModel):
    word: str
    verdict: str
    score: float
    supported_claims: list[str]
    unsupported_claims: list[str]
    missing_citations: list[str]
    warnings: list[str]
    evidence_summary: dict


class SourceResponse(BaseModel):
    slug: str
    short_name: str
    authority_tier: int
    year: int | None = None
    category: str | None = None

    model_config = {"from_attributes": True}
