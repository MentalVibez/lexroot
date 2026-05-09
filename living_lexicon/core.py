"""
WordHistorian — the main public class of the living-lexicon SDK.

Orchestrates store + LLM + prompt building. Returns typed models rather than
raw dicts, so consumer projects get IDE completion and type safety.

Usage:
    from living_lexicon import WordHistorian

    # Embedded (Neo4j + Ollama)
    h = WordHistorian()
    ctx = h.context("prevent")           # no LLM needed
    drift = h.explain("prevent", context="biblical")

    # Remote HTTP instance
    h = WordHistorian.from_url("http://lexicon-service:8000")
    ctx = h.context("charity")
"""
from __future__ import annotations
import re

from living_lexicon.config import LexiconConfig
from living_lexicon.exceptions import EraNotFoundError, LLMError, SourceNotFoundError, WordNotFoundError
from living_lexicon.models import (
    DriftExplanation, EraContext, EraRecord, EtymologyClaimInfo, RetrievalBundle, RootInfo,
    SourceInfo, WordContext,
    FactCheckResult, TeachingCard, WordDetectiveResult,
)
from living_lexicon.prompts import build_drift_prompt, build_era_explanation_prompt
from living_lexicon.protocols import EtymologyStore, LLMProvider
from living_lexicon.word_detective import detect_spelling_rules


def _to_source(d: dict) -> SourceInfo:
    return SourceInfo(
        slug=d.get("slug") or "",
        short_name=d.get("short_name") or d.get("slug") or "",
        authority_tier=d.get("authority_tier") or 99,
        year=d.get("year"),
        category=d.get("category"),
    )


def _to_era_record(d: dict) -> EraRecord:
    src = None
    if d.get("source_slug") or d.get("slug"):
        src = SourceInfo(
            slug=d.get("source_slug") or d.get("slug") or "",
            short_name=d.get("source_short_name") or "",
            authority_tier=d.get("source_tier") or 99,
        )
    return EraRecord(
        era_name=d.get("era_name") or "",
        start_year=d.get("era_start") or 0,
        end_year=d.get("era_end") or 0,
        meaning=d.get("meaning"),
        usage_example=d.get("usage_example"),
        source=src,
    )


def _claim_score(claim: dict) -> float:
    tier = claim.get("source_tier") or 99
    confidence = (claim.get("confidence") or "medium").lower()
    score = max(0.0, 1.0 - ((tier - 1) * 0.15))
    score += {"high": 0.2, "medium": 0.0, "low": -0.2}.get(confidence, -0.05)
    if claim.get("is_reconstructed"):
        score -= 0.05
    if claim.get("intermediate_path"):
        score += 0.05
    return round(max(0.0, min(score, 1.0)), 3)


def _to_claim(d: dict) -> EtymologyClaimInfo:
    return EtymologyClaimInfo(
        id=d.get("id") or "",
        relation_type=d.get("relation_type") or "",
        source_form=d.get("source_form") or "",
        source_language=d.get("source_language") or "",
        confidence=d.get("confidence") or "medium",
        score=_claim_score(d),
        source_slug=d.get("source_slug"),
        source_short_name=d.get("source_short_name"),
        source_tier=d.get("source_tier") or 99,
        note=d.get("note"),
        original_form=d.get("original_form"),
        is_reconstructed=bool(d.get("is_reconstructed")),
        intermediate_path=list(d.get("intermediate_path") or []),
    )


RELIGIOUS_SOURCE_TRADITIONS = {
    "kjv-1611": "Christianity",
    "authorized-1769": "Christianity",
    "wycliffe-1382": "Christianity",
    "tyndale-1526": "Christianity",
    "geneva-bible-1560": "Christianity",
    "coverdale-1535": "Christianity",
    "vulgate-latin": "Christianity",
    "internet-sacred-text-archive": "World religions",
}


def _evidence_label(bundle: RetrievalBundle) -> str:
    if bundle.evidence_summary.get("has_high_authority_source"):
        return "well-attested"
    if bundle.evidence_summary.get("requires_uncertainty_language"):
        return "machine-derived or lexical-source evidence; needs review"
    if bundle.claims:
        return "supported by current graph evidence"
    return "insufficient evidence"


def _curriculum_tags(bundle: RetrievalBundle) -> list[str]:
    tags: set[str] = set()
    source_slugs = {source.slug for source in bundle.sources}
    source_slugs.update(claim.source_slug or "" for claim in bundle.claims)
    for slug in source_slugs:
        if slug in RELIGIOUS_SOURCE_TRADITIONS:
            tags.add("religious-texts")
            tags.add(RELIGIOUS_SOURCE_TRADITIONS[slug].casefold().replace(" ", "-"))
        if slug == "shakespeare":
            tags.add("shakespeare")
        if slug in {"oed-2e", "mec-corpus", "bosworth-toller", "hall-1894"}:
            tags.add("historical-english")
    for claim in bundle.claims:
        language = claim.source_language.lower()
        if "latin" in language:
            tags.add("latin-roots")
        if "greek" in language:
            tags.add("greek-roots")
        if "old english" in language:
            tags.add("old-english-roots")
        if claim.is_reconstructed:
            tags.add("reconstructed-root")
    if any(era.meaning for era in bundle.timeline):
        tags.add("semantic-drift")
    return sorted(tag for tag in tags if tag)


def _reading_style(level: str) -> dict[str, str]:
    return {
        "middle_school": {
            "prompt": "What did this word used to mean, and what does it mean now?",
            "activity": "Match the older meaning to the modern meaning.",
        },
        "high_school": {
            "prompt": "Why might a modern reader misunderstand this word in an older text?",
            "activity": "Spot the false friend and rewrite the sentence in modern English.",
        },
        "college": {
            "prompt": "Which source claim best explains the semantic shift, and what uncertainty remains?",
            "activity": "Compare the top claim with a lower-confidence claim and justify which one you would cite.",
        },
        "scholarly": {
            "prompt": "Evaluate the etymological claim, source tier, reconstruction status, and attestation coverage.",
            "activity": "Write a source-aware etymology note with explicit uncertainty language.",
        },
    }.get(level, {
        "prompt": "Why might a reader misunderstand this word?",
        "activity": "Explain the old meaning and the modern meaning.",
    })


def _contains(text: str, value: str | None) -> bool:
    if not value:
        return False
    value = value.strip()
    if not value:
        return False
    pattern = r"(?<![A-Za-z])" + re.escape(value.lower()) + r"(?![A-Za-z])"
    return bool(re.search(pattern, text.lower()))


def _has_citation(text: str, slug: str | None, short_name: str | None) -> bool:
    return _contains(text, slug) or _contains(text, short_name) or bool(short_name and f"[{short_name.lower()}]" in text.lower())


def _unsupported_root_assertions(text: str, bundle: RetrievalBundle) -> list[str]:
    known_roots = {claim.source_form.lower() for claim in bundle.claims if claim.source_form}
    if bundle.context.root.name:
        known_roots.add(bundle.context.root.name.lower())
    snippets = re.findall(r"(?:from|root(?:ed)? in|derived from|comes from)\s+([A-Za-z*][A-Za-z*'\-]{1,40})", text, flags=re.I)
    unsupported = []
    for snippet in snippets:
        if snippet.lower().strip("*") not in {root.strip("*") for root in known_roots}:
            unsupported.append(f"Root/source form '{snippet}' is not in the retrieval bundle.")
    return unsupported


class WordHistorian:
    """
    The main entry point for the living-lexicon SDK.

    Can be instantiated with explicit providers, from environment variables
    (the default), or pointed at a remote HTTP instance via from_url().
    """

    def __init__(
        self,
        store: EtymologyStore | None = None,
        llm: LLMProvider | None = None,
        config: LexiconConfig | None = None,
    ):
        # Lazy imports keep provider deps optional at import time
        if store is None:
            from living_lexicon.providers.stores.neo4j_store import Neo4jStore
            store = Neo4jStore.from_env()
        if llm is None:
            try:
                from living_lexicon.providers.llm.ollama import OllamaProvider
                llm = OllamaProvider.from_env()
            except ImportError:
                llm = None  # LLM is optional for context/timeline queries

        self._store = store
        self._llm = llm

    @classmethod
    def from_url(cls, base_url: str, timeout: float = 10.0) -> "WordHistorian":
        """
        Connect to a remote Living Lexicon server.
        LLM calls are handled server-side via the /drift and /era endpoints.
        No local Neo4j or Ollama needed.
        """
        from living_lexicon.providers.stores.http_store import HttpStore
        return cls(store=HttpStore(base_url, timeout=timeout), llm=None)

    # ── Read methods ──────────────────────────────────────────────────────────

    def context(self, word: str) -> WordContext:
        """Core lookup: definition, root, cognates, sources. No LLM needed."""
        data = self._store.get_word(word)
        if not data:
            raise WordNotFoundError(word)
        sources = [_to_source(s) for s in self._store.get_word_sources(word)]
        return WordContext(
            word=data["name"],
            language=data.get("language") or "English",
            definition=data.get("definition") or "",
            root=RootInfo(
                name=data.get("root") or "",
                meaning=data.get("root_meaning") or "",
                origin_language=data.get("root_origin") or "",
            ),
            cognates=list(data.get("cognates") or []),
            sources=sources,
        )

    def timeline(self, word: str) -> list[EraRecord]:
        """
        All 7 canonical eras with this word's meaning (or None) for each.
        Filled dot = documented, hollow = no record. No LLM needed.
        """
        if not self._store.get_word(word):
            raise WordNotFoundError(word)
        return [_to_era_record(e) for e in self._store.get_era_timeline(word)]

    def etymology_claims(self, word: str) -> list[EtymologyClaimInfo]:
        """Source-specific etymology claims, ranked for AI grounding."""
        if not self._store.get_word(word):
            raise WordNotFoundError(word)
        claims = [_to_claim(c) for c in self._store.get_etymology_claims(word)]
        return sorted(claims, key=lambda c: c.score, reverse=True)

    def retrieval_bundle(self, word: str) -> RetrievalBundle:
        """
        Deterministic facts for LLM prompts, evals, and guardrails.
        No generated prose. Claims are ranked but not collapsed.
        """
        context = self.context(word)
        claims = self.etymology_claims(word)
        timeline = self.timeline(word)
        sources = context.sources
        documented_eras = [era.era_name for era in timeline if era.meaning]
        evidence_summary = {
            "claim_count": len(claims),
            "top_claim_score": claims[0].score if claims else 0.0,
            "has_high_authority_source": any((claim.source_tier or 99) <= 2 for claim in claims),
            "has_only_machine_or_lexical_sources": bool(claims) and all((claim.source_tier or 99) >= 3 for claim in claims),
            "documented_eras": documented_eras,
            "requires_uncertainty_language": not claims or all((claim.source_tier or 99) >= 3 for claim in claims),
        }
        return RetrievalBundle(
            word=context.word,
            context=context,
            claims=claims,
            timeline=timeline,
            sources=sources,
            evidence_summary=evidence_summary,
        )

    def teaching_card(self, word: str, level: str = "high_school") -> TeachingCard:
        """Classroom-ready deterministic teaching object."""
        bundle = self.retrieval_bundle(word)
        top_claim = bundle.claims[0] if bundle.claims else None
        documented = [era for era in bundle.timeline if era.meaning]
        earliest = documented[0] if documented else None
        style = _reading_style(level)
        old_meaning = earliest.meaning if earliest else (top_claim.note if top_claim else "No historical meaning is documented yet.")
        old_era = earliest.era_name if earliest else "earlier evidence"
        modern = bundle.context.definition
        best_origin = (
            f"{top_claim.source_form} ({top_claim.source_language})"
            if top_claim else
            f"{bundle.context.root.name} ({bundle.context.root.origin_language})"
        )
        misconception = (
            f"Do not assume '{bundle.word}' meant exactly '{modern}' in older translated or historical texts."
            if earliest else
            f"The current graph does not yet have enough historical evidence to teach '{bundle.word}' as a confirmed false friend."
        )
        question_context = "religious or historical text" if "religious-texts" in _curriculum_tags(bundle) else "older text"
        card = TeachingCard(
            word=bundle.word,
            level=level,
            modern_definition=modern,
            best_origin=best_origin,
            then_vs_now={
                "then": old_meaning,
                "then_context": old_era,
                "now": modern,
                "one_sentence_correction": f"In {question_context}, check whether '{bundle.word}' carries an older sense before reading it with today's meaning.",
            },
            misconception_check=misconception,
            classroom_example={
                "source_sentence": earliest.usage_example if earliest and earliest.usage_example else "",
                "modern_paraphrase": f"Read '{bundle.word}' as: {old_meaning}",
                "teacher_prompt": style["prompt"],
            },
            discussion_questions=[
                style["prompt"],
                f"What clue in the source or root helps you avoid the modern assumption about '{bundle.word}'?",
                "What evidence would make this explanation stronger?",
            ],
            activity={
                "type": "semantic-drift-check",
                "instructions": style["activity"],
                "answer_key_hint": old_meaning,
            },
            curriculum_tags=_curriculum_tags(bundle),
            content_warnings=[],
            evidence_label=_evidence_label(bundle),
            religious_text_note=(
                "Religion-agnostic mode: compare translated sacred texts across traditions without privileging one canon. "
                "Use Internet Sacred Text Archive material only from local/permitted copies with attribution."
                if "religious-texts" in _curriculum_tags(bundle) else None
            ),
        )
        return card

    def fact_check_answer(self, word: str, answer: str, strict: bool = True) -> FactCheckResult:
        """Deterministically check an answer against the retrieval bundle."""
        bundle = self.retrieval_bundle(word)
        text = answer or ""
        supported: list[str] = []
        unsupported: list[str] = []
        missing_citations: list[str] = []
        warnings: list[str] = []

        if _contains(text, bundle.context.definition):
            supported.append("Modern definition is represented.")

        for claim in bundle.claims[:5]:
            claim_bits = []
            if _contains(text, claim.source_form):
                claim_bits.append(f"source form '{claim.source_form}'")
            if _contains(text, claim.source_language):
                claim_bits.append(f"source language '{claim.source_language}'")
            if claim_bits:
                supported.append(f"Etymology claim mentions {', '.join(claim_bits)}.")
                if strict and not _has_citation(text, claim.source_slug, claim.source_short_name):
                    missing_citations.append(
                        f"Claim about '{claim.source_form}' should cite {claim.source_short_name or claim.source_slug or 'its source'}."
                    )

        for era in bundle.timeline:
            if era.meaning and _contains(text, era.era_name):
                supported.append(f"Historical era '{era.era_name}' is represented.")

        mentioned_cognates = [c for c in bundle.context.cognates[:10] if _contains(text, c)]
        if mentioned_cognates:
            supported.append(f"Cognates/related words represented: {', '.join(mentioned_cognates)}.")

        unsupported.extend(_unsupported_root_assertions(text, bundle))

        known_languages = {claim.source_language.lower() for claim in bundle.claims}
        if bundle.context.root.origin_language:
            known_languages.add(bundle.context.root.origin_language.lower())
        for lang in ["latin", "greek", "old english", "middle english", "old french", "arabic", "hebrew", "sanskrit"]:
            if lang in text.lower() and not any(lang in known for known in known_languages):
                unsupported.append(f"Language '{lang}' is mentioned but not supported by current claims.")

        if bundle.evidence_summary.get("requires_uncertainty_language"):
            uncertainty_markers = ["suggests", "may", "might", "likely", "machine-derived", "needs review", "uncertain", "current evidence"]
            if not any(marker in text.lower() for marker in uncertainty_markers):
                warnings.append("Answer should use uncertainty language because current evidence is limited or machine-derived.")

        if any(claim.is_reconstructed for claim in bundle.claims) and "reconstructed" not in text.lower() and "not directly attested" not in text.lower():
            warnings.append("Answer mentions reconstructed evidence but does not clearly mark it as reconstructed/not directly attested.")

        total_checks = max(1, len(supported) + len(unsupported) + len(missing_citations) + len(warnings))
        score = round(max(0.0, (len(supported) - len(unsupported) - (0.5 * len(missing_citations)) - (0.25 * len(warnings))) / total_checks), 3)
        if unsupported:
            verdict = "unsupported"
        elif missing_citations:
            verdict = "needs citations"
        elif warnings:
            verdict = "mostly grounded"
        elif supported:
            verdict = "grounded"
        else:
            verdict = "insufficient evidence"

        return FactCheckResult(
            word=bundle.word,
            verdict=verdict,
            score=score,
            supported_claims=supported,
            unsupported_claims=unsupported,
            missing_citations=missing_citations,
            warnings=warnings,
            evidence_summary=bundle.evidence_summary,
        )

    def word_detective(self, word: str) -> WordDetectiveResult:
        """
        Identify whether spelling follows a standard phonics rule or preserves
        a historical root exception. Deterministic; no LLM required.
        """
        bundle = self.retrieval_bundle(word)
        detected = detect_spelling_rules(bundle.word, bundle.context.root, bundle.claims)
        return WordDetectiveResult(word=bundle.word, **detected)

    def explain(self, word: str, context: str | None = None) -> DriftExplanation:
        """
        AI explanation of how this word's meaning has shifted over time.
        Requires an LLM provider. context: 'biblical' | 'legal' | 'literary' | 'medical'
        """
        if self._llm is None:
            raise LLMError(
                "No LLM provider configured. "
                "Pass llm=OllamaProvider() to WordHistorian(), or use from_url() "
                "to delegate LLM calls to a remote server."
            )
        data = self._store.get_word(word)
        if not data:
            raise WordNotFoundError(word)

        era_meanings = self._store.get_word_era_meanings(word)
        prompt = build_drift_prompt(
            word=data["name"],
            root=data.get("root") or "",
            root_meaning=data.get("root_meaning") or "",
            root_origin=data.get("root_origin") or "",
            cognates=list(data.get("cognates") or [])[:5],
            definition=data.get("definition") or "",
            context_hint=context,
            era_meanings=era_meanings or None,
        )
        ai_text = self._llm.generate(prompt)
        era_timeline = [_to_era_record(e) for e in self._store.get_era_timeline(word)]

        return DriftExplanation(
            word=word,
            context_hint=context,
            ai_explanation=ai_text,
            root=RootInfo(
                name=data.get("root") or "",
                meaning=data.get("root_meaning") or "",
                origin_language=data.get("root_origin") or "",
            ),
            era_timeline=era_timeline,
        )

    def in_era(self, word: str, era: str, snippet: str | None = None) -> EraContext:
        """
        What did this word mean in a specific historical era?
        Degrades gracefully if no documented record — AI reasons from root.
        era accepts slug form ('early-modern-english') or canonical ('Early Modern English').
        """
        if self._llm is None:
            raise LLMError(
                "No LLM provider configured. "
                "Pass llm=OllamaProvider() to WordHistorian(), or use from_url()."
            )
        canonical_era = era.replace("-", " ").title()
        graph_data = self._store.get_word_in_era(word, canonical_era)

        if graph_data is None:
            word_data = self._store.get_word(word)
            if not word_data:
                raise WordNotFoundError(word)
            graph_data = {
                "name": word,
                "modern_definition": word_data.get("definition", ""),
                "era_name": canonical_era,
                "era_start": 0, "era_end": 0, "era_summary": "",
                "historical_meaning": None, "usage_example": None,
                "root": word_data.get("root", ""), "root_meaning": word_data.get("root_meaning", ""),
                "source_short_name": None,
            }

        prompt = build_era_explanation_prompt(
            word=word,
            era_name=canonical_era,
            era_start=graph_data.get("era_start") or 0,
            era_end=graph_data.get("era_end") or 0,
            era_summary=graph_data.get("era_summary") or "",
            historical_meaning=graph_data.get("historical_meaning"),
            usage_example=graph_data.get("usage_example"),
            modern_definition=graph_data.get("modern_definition") or "",
            root=graph_data.get("root") or "",
            root_meaning=graph_data.get("root_meaning") or "",
            passage_snippet=snippet,
            source_short_name=graph_data.get("source_short_name"),
        )
        ai_text = self._llm.generate(prompt)

        src = None
        if graph_data.get("source_short_name"):
            src = SourceInfo(
                slug="",
                short_name=graph_data["source_short_name"],
                authority_tier=99,
            )

        return EraContext(
            word=word,
            era_name=canonical_era,
            historical_meaning=graph_data.get("historical_meaning"),
            usage_example=graph_data.get("usage_example"),
            modern_definition=graph_data.get("modern_definition") or "",
            ai_explanation=ai_text,
            source=src,
        )

    def search(self, query: str, limit: int = 10) -> list[WordContext]:
        """Full-text search. Returns lightweight WordContext objects (no sources fetched)."""
        results = self._store.search(query, limit)
        out = []
        for r in results:
            out.append(WordContext(
                word=r.get("name") or "",
                language=r.get("language") or "English",
                definition=r.get("definition") or "",
                root=RootInfo(name="", meaning="", origin_language=""),
                cognates=[],
                sources=[],
            ))
        return out

    # ── Source catalog ────────────────────────────────────────────────────────

    def sources(self) -> list[SourceInfo]:
        """Full catalog of all scholarly sources, sorted by authority tier."""
        return [_to_source(s) for s in self._store.get_all_sources()]

    def source(self, slug: str) -> SourceInfo:
        """Metadata for a specific source by slug."""
        data = self._store.get_source(slug)
        if not data:
            raise SourceNotFoundError(slug)
        return _to_source(data)

    def words_by_source(self, slug: str, limit: int = 20) -> list[str]:
        """Words attested in a specific source."""
        return [r["name"] for r in self._store.get_words_by_source(slug, limit)]
