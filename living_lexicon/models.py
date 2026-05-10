"""
Pure data models — the SDK's return types and the contract between providers and callers.
No external dependencies: these dataclasses are safe to import anywhere.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class SourceInfo:
    slug: str
    short_name: str
    authority_tier: int
    year: int | None = None
    category: str | None = None


@dataclass
class RootInfo:
    name: str
    meaning: str
    origin_language: str


@dataclass
class EraRecord:
    era_name: str
    start_year: int
    end_year: int
    meaning: str | None = None
    usage_example: str | None = None
    source: SourceInfo | None = None


@dataclass
class WordContext:
    """Core word data — definition, root, cognates, and attesting sources. No LLM needed."""
    word: str
    language: str
    definition: str
    root: RootInfo
    cognates: list[str] = field(default_factory=list)
    sources: list[SourceInfo] = field(default_factory=list)


@dataclass
class DriftExplanation:
    """AI-generated explanation of how a word's meaning shifted over time."""
    word: str
    context_hint: str | None
    ai_explanation: str
    root: RootInfo
    era_timeline: list[EraRecord] = field(default_factory=list)


@dataclass
class EraContext:
    """What a word meant in a specific historical era, with AI explanation."""
    word: str
    era_name: str
    historical_meaning: str | None
    usage_example: str | None
    modern_definition: str
    ai_explanation: str
    source: SourceInfo | None = None


@dataclass
class EtymologyClaimInfo:
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
    original_form: str | None = None
    is_reconstructed: bool = False
    intermediate_path: list[str] = field(default_factory=list)


@dataclass
class RetrievalBundle:
    word: str
    context: WordContext
    claims: list[EtymologyClaimInfo] = field(default_factory=list)
    timeline: list[EraRecord] = field(default_factory=list)
    sources: list[SourceInfo] = field(default_factory=list)
    evidence_summary: dict = field(default_factory=dict)


@dataclass
class TeachingCard:
    word: str
    level: str
    modern_definition: str
    best_origin: str
    then_vs_now: dict
    misconception_check: str
    classroom_example: dict
    discussion_questions: list[str] = field(default_factory=list)
    activity: dict = field(default_factory=dict)
    curriculum_tags: list[str] = field(default_factory=list)
    content_warnings: list[str] = field(default_factory=list)
    evidence_label: str = "needs review"
    religious_text_note: str | None = None


@dataclass
class FactCheckResult:
    word: str
    verdict: str
    score: float
    supported_claims: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    missing_citations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    evidence_summary: dict = field(default_factory=dict)


@dataclass
class WordDetectiveResult:
    word: str
    classification: str
    confidence: float
    summary: str
    root_clue: dict
    phonics_rule_applies: bool | None = None
    standard_phonics_rule: str | None = None
    spelling_history_type: str | None = None
    exception_reason: str | None = None
    spelling_explanation: str | None = None
    root_influence: str | None = None
    evidence_grade: str | None = None
    confidence_reason: str | None = None
    standard_rules: list[dict] = field(default_factory=list)
    historical_exceptions: list[dict] = field(default_factory=list)
