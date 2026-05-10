"""
Zero-dependency testing utilities for the living-lexicon SDK.

Provides InMemoryStore (satisfies EtymologyStore), StubLLMProvider (satisfies
LLMProvider), and WordHistorianFactory for building pre-loaded historians.

No pytest, no databases, no network required. Safe to use in any test framework
or in plain Python scripts.

Usage:
    from living_lexicon.testing import InMemoryStore, StubLLMProvider, WordHistorianFactory

    store = InMemoryStore(
        words={
            "prevent": {
                "name": "prevent",
                "language": "English",
                "definition": "To stop something from happening.",
                "root": "praevenire",
                "root_meaning": "to come before",
                "root_origin": "Latin",
                "cognates": ["prevention", "preventive"],
            }
        },
        sources=[
            {"slug": "oed-2e", "short_name": "OED", "authority_tier": 2, "year": 1989}
        ],
    )
    h = WordHistorianFactory.build(store=store, llm_response="It meant 'to come before'.")
    ctx = h.context("prevent")
"""
from __future__ import annotations

from typing import Any


class InMemoryStore:
    """
    In-memory EtymologyStore backed by plain Python dicts.

    Satisfies the full EtymologyStore protocol (all 14 methods) without Neo4j,
    httpx, or any optional dependency. Ideal for unit tests.

    Constructor parameters
    ----------------------
    words : dict[str, dict]
        Keyed by lowercase word name. Each value is a dict with keys matching
        what Neo4jStore.get_word() returns:
            name, language, definition, root, root_meaning, root_origin, cognates
        All keys are optional; missing ones produce empty strings or [].

    sources : list[dict]
        Each dict matches what Neo4jStore.get_all_sources() returns:
            slug, short_name, authority_tier, year (optional), category (optional)

    era_timelines : dict[str, list[dict]]  (optional)
        Keyed by lowercase word name. Each value is a list of era dicts with keys:
            era_name, era_start, era_end, meaning, usage_example
        If a word has no key here, get_era_timeline() returns [].

    era_meanings : dict[str, list[dict]]  (optional)
        Same shape as era_timelines; used by get_word_era_meanings().
        Falls back to era_timelines[word] if absent.

    etymology_claims : dict[str, list[dict]]  (optional)
        Keyed by lowercase word name. Each value is a list of claim dicts matching
        what Neo4jStore.get_etymology_claims() returns.

    word_sources : dict[str, list[dict]]  (optional)
        Per-word source override. If absent, all sources are returned for every word.

    eras : list[dict]  (optional)
        Global era nodes for get_era_by_year(). Each dict has start_year, end_year, name.
    """

    def __init__(
        self,
        words: dict[str, dict] | None = None,
        sources: list[dict] | None = None,
        era_timelines: dict[str, list[dict]] | None = None,
        era_meanings: dict[str, list[dict]] | None = None,
        etymology_claims: dict[str, list[dict]] | None = None,
        word_sources: dict[str, list[dict]] | None = None,
        eras: list[dict] | None = None,
    ):
        self._words: dict[str, dict] = {k.lower(): v for k, v in (words or {}).items()}
        self._sources: list[dict] = sources or []
        self._era_timelines: dict[str, list[dict]] = {k.lower(): v for k, v in (era_timelines or {}).items()}
        self._era_meanings: dict[str, list[dict]] = {k.lower(): v for k, v in (era_meanings or {}).items()}
        self._etymology_claims: dict[str, list[dict]] = {k.lower(): v for k, v in (etymology_claims or {}).items()}
        self._word_sources: dict[str, list[dict]] = {k.lower(): v for k, v in (word_sources or {}).items()}
        self._eras: list[dict] = eras or []

    # ── Word queries ──────────────────────────────────────────────────────────

    def get_word(self, word: str) -> dict | None:
        return self._words.get(word.lower())

    def get_word_tree(self, word: str) -> dict:
        return {}

    def get_cognates(self, word: str) -> list[dict]:
        return []

    def get_etymology_claims(self, word: str) -> list[dict]:
        return self._etymology_claims.get(word.lower(), [])

    def search(self, query: str, limit: int = 10) -> list[dict]:
        q = query.lower()
        results = []
        for key, word_data in self._words.items():
            if q in key or q in (word_data.get("definition") or "").lower():
                results.append(word_data)
                if len(results) >= limit:
                    break
        return results

    # ── Era queries ───────────────────────────────────────────────────────────

    def get_word_era_meanings(self, word: str) -> list[dict]:
        key = word.lower()
        return self._era_meanings.get(key, self._era_timelines.get(key, []))

    def get_era_timeline(self, word: str) -> list[dict]:
        return self._era_timelines.get(word.lower(), [])

    def get_word_in_era(self, word: str, era_name: str) -> dict | None:
        for era in self._era_timelines.get(word.lower(), []):
            if era.get("era_name", "").lower() == era_name.lower():
                word_data = self._words.get(word.lower()) or {}
                return {
                    "name": word_data.get("name", word),
                    "modern_definition": word_data.get("definition", ""),
                    "era_name": era.get("era_name", ""),
                    "era_start": era.get("era_start", 0),
                    "era_end": era.get("era_end", 0),
                    "era_summary": "",
                    "historical_meaning": era.get("meaning"),
                    "usage_example": era.get("usage_example"),
                    "root": word_data.get("root", ""),
                    "root_meaning": word_data.get("root_meaning", ""),
                    "source_short_name": era.get("source_short_name"),
                }
        return None

    def get_era_by_year(self, year: int) -> dict | None:
        for era in self._eras:
            if era.get("start_year", 0) <= year <= era.get("end_year", 0):
                return era
        return None

    def get_words_by_era(self, era_name: str, limit: int = 20) -> list[dict]:
        results = []
        for word_key, timelines in self._era_timelines.items():
            for era in timelines:
                if era.get("era_name", "").lower() == era_name.lower() and era.get("meaning"):
                    word_data = self._words.get(word_key) or {}
                    results.append({
                        "name": word_data.get("name", word_key),
                        "modern_definition": word_data.get("definition", ""),
                        "historical_meaning": era.get("meaning"),
                    })
                    break
            if len(results) >= limit:
                break
        return results

    # ── Source queries ────────────────────────────────────────────────────────

    def get_word_sources(self, word: str) -> list[dict]:
        if word.lower() in self._word_sources:
            return self._word_sources[word.lower()]
        return self._sources

    def get_all_sources(self) -> list[dict]:
        return list(self._sources)

    def get_source(self, slug: str) -> dict | None:
        for s in self._sources:
            if s.get("slug") == slug:
                return s
        return None

    def get_words_by_source(self, slug: str, limit: int = 20) -> list[dict]:
        results = []
        for key, word_data in self._words.items():
            results.append({"name": word_data.get("name", key), "definition": word_data.get("definition", "")})
            if len(results) >= limit:
                break
        return results


class StubLLMProvider:
    """
    Deterministic stub for the LLMProvider protocol.

    Returns a fixed response string or cycles through a list of responses
    so tests never call a real LLM.

    Usage:
        stub = StubLLMProvider("The word originally meant X.")
        h = WordHistorian(store=store, llm=stub)
        drift = h.explain("prevent")
        assert "originally meant" in drift.ai_explanation

    Cycling example (multiple sequential LLM calls in one test):
        stub = StubLLMProvider(["First response.", "Second response."])
    """

    def __init__(self, response: str | list[str] = "Stub LLM response."):
        self._responses: list[str] = [response] if isinstance(response, str) else list(response)
        self._call_count = 0

    def generate(self, prompt: str) -> str:
        idx = self._call_count % len(self._responses)
        self._call_count += 1
        return self._responses[idx]

    @property
    def call_count(self) -> int:
        return self._call_count

    def reset(self) -> None:
        self._call_count = 0


class WordHistorianFactory:
    """
    Convenience factory for building pre-loaded WordHistorian instances in tests.

    Accepts seed data for words/sources and a fixed LLM response string.

    Usage:
        h = WordHistorianFactory.build(
            words={"prevent": {"name": "prevent", "definition": "...", "root": "praevenire", ...}},
            sources=[{"slug": "oed-2e", "short_name": "OED", "authority_tier": 2}],
            llm_response="Stub explanation.",
        )
        result = h.context("prevent")
    """

    @staticmethod
    def build(
        words: dict[str, dict] | None = None,
        sources: list[dict] | None = None,
        era_timelines: dict[str, list[dict]] | None = None,
        etymology_claims: dict[str, list[dict]] | None = None,
        llm_response: str | list[str] = "Stub LLM response.",
        store: Any = None,
        llm: Any = None,
    ) -> Any:
        # Lazy import avoids circular dependency: testing.py is imported by __init__.py,
        # which core.py also indirectly imports.
        from living_lexicon.core import WordHistorian
        _store = store or InMemoryStore(
            words=words,
            sources=sources,
            era_timelines=era_timelines,
            etymology_claims=etymology_claims,
        )
        _llm = llm or StubLLMProvider(llm_response)
        return WordHistorian(store=_store, llm=_llm)
