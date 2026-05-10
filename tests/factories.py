"""
Test data factories for Living Lexicon.

Produces plain dicts matching the request/response shapes of API endpoints
and the seed structures expected by InMemoryStore.

All factories follow the same pattern:
    WordPayloadFactory.build(**overrides)       → dict
    WordPayloadFactory.build_batch(n, **overrides) → list[dict]

No external dependencies. No database writes. No network calls.
"""
from __future__ import annotations

import itertools
from typing import Any

_counter = itertools.count(1)


def _next_id() -> int:
    return next(_counter)


# ---------------------------------------------------------------------------
# API payload factories — for HTTP endpoint tests (PUT /pg/word, etc.)
# ---------------------------------------------------------------------------

class WordPayloadFactory:
    """Builds payload dicts for PUT /pg/word requests."""

    DEFAULTS: dict[str, Any] = {
        "word": "testword",
        "phonemes": "/ˈtɛst.wɜːd/",
        "etymology_root": "testus",
        "definition": "A word used for testing.",
        "origin_language": "Latin",
        "language_family": "Indo-European (Italic)",
        "historical_context": "A hypothetical Latin origin for test purposes.",
    }

    @classmethod
    def build(cls, **overrides: Any) -> dict[str, Any]:
        payload = dict(cls.DEFAULTS)
        payload.update(overrides)
        if "word" not in overrides:
            payload["word"] = f"testword_{_next_id()}"
        return payload

    @classmethod
    def build_batch(cls, n: int, **overrides: Any) -> list[dict[str, Any]]:
        return [cls.build(**overrides) for _ in range(n)]


class SensePayloadFactory:
    """Builds payload dicts for PUT /pg/sense requests."""

    DEFAULTS: dict[str, Any] = {
        "sense_id": "sense-PLACEHOLDER",
        "word": "nice",
        "entry_type": "word",
        "part_of_speech": "adjective",
        "definition": "Foolish or ignorant.",
        "meaning_type": "attested",
        "register": "obsolete",
        "domain": "general",
        "era_name": "Middle English",
        "first_attested_year": 1300,
        "last_attested_year": 1500,
        "source_slug": "middle-english-dictionary",
        "confidence": "high",
        "confidence_reason": "Historical dictionary evidence with citation.",
        "evidence_grade": "B",
        "citation": "MED nice adj.",
        "entry_headword": "nice",
        "semantic_change_type": "pejoration",
        "origin_status": "attested",
        "usage_region": "England",
        "usage_register": "obsolete",
    }

    @classmethod
    def build(cls, **overrides: Any) -> dict[str, Any]:
        payload = dict(cls.DEFAULTS)
        payload.update(overrides)
        if "sense_id" not in overrides:
            n = _next_id()
            word = payload.get("word", "word")
            era = (payload.get("era_name") or "era").lower().replace(" ", "-")
            payload["sense_id"] = f"{word}-{era}-{n}"
        return payload

    @classmethod
    def build_batch(cls, n: int, **overrides: Any) -> list[dict[str, Any]]:
        return [cls.build(**overrides) for _ in range(n)]


class AttestationPayloadFactory:
    """Builds payload dicts for POST /pg/attestation requests."""

    DEFAULTS: dict[str, Any] = {
        "sense_id": "sense-PLACEHOLDER",
        "word": "nice",
        "quote": "A compact fair-use quotation.",
        "quote_year": 1390,
        "quote_author": "Geoffrey Chaucer",
        "quote_work": "Canterbury Tales",
        "source_slug": "middle-english-dictionary",
        "attestation_type": "quotation",
        "citation": "MED nice adj.",
        "evidence_grade": "A",
        "confidence_reason": "Dated quotation evidence.",
        "entry_headword": "nice",
        "review_status": "reviewed",
    }

    @classmethod
    def build(cls, **overrides: Any) -> dict[str, Any]:
        payload = dict(cls.DEFAULTS)
        payload.update(overrides)
        return payload

    @classmethod
    def build_batch(cls, n: int, **overrides: Any) -> list[dict[str, Any]]:
        return [cls.build(**overrides) for _ in range(n)]


# ---------------------------------------------------------------------------
# InMemoryStore seed factories — for SDK unit tests
# ---------------------------------------------------------------------------

class WordSeedFactory:
    """
    Builds seed dicts for InMemoryStore(words={...}).

    The dict shape matches what Neo4jStore.get_word() returns,
    which is what WordHistorian.context() reads.
    """

    DEFAULTS: dict[str, Any] = {
        "name": "testword",
        "language": "English",
        "definition": "A word used for testing.",
        "root": "testus",
        "root_meaning": "to test",
        "root_origin": "Latin",
        "cognates": [],
    }

    @classmethod
    def build(cls, **overrides: Any) -> dict[str, Any]:
        seed = dict(cls.DEFAULTS)
        seed.update(overrides)
        return seed

    @classmethod
    def build_keyed(cls, word: str, **overrides: Any) -> dict[str, dict[str, Any]]:
        """Return {word: seed_dict} ready to unpack into InMemoryStore(words=...)."""
        return {word.lower(): cls.build(name=word, **overrides)}


class EraTimelineFactory:
    """Builds era timeline lists for InMemoryStore(era_timelines={...})."""

    CANONICAL_ERAS: list[tuple[str, int, int]] = [
        ("Old English", -700, 1066),
        ("Middle English", 1066, 1470),
        ("Early Modern English", 1470, 1700),
        ("Late Modern English", 1700, 1900),
        ("20th Century", 1900, 2000),
    ]

    @classmethod
    def build_single(
        cls,
        era_name: str = "Middle English",
        start_year: int = 1066,
        end_year: int = 1470,
        meaning: str | None = "An older meaning.",
        usage_example: str | None = None,
    ) -> dict[str, Any]:
        return {
            "era_name": era_name,
            "era_start": start_year,
            "era_end": end_year,
            "meaning": meaning,
            "usage_example": usage_example,
        }

    @classmethod
    def build_timeline(
        cls, word: str, meanings: dict[str, str | None]
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Build a full era timeline keyed by word for InMemoryStore(era_timelines=...).

        meanings: {era_name: meaning_string_or_None}
        Example:
            EraTimelineFactory.build_timeline("prevent", {
                "Middle English": "to come before",
                "Early Modern English": "to hinder",
            })
        """
        timeline = [
            cls.build_single(
                era_name=era_name,
                start_year=start_year,
                end_year=end_year,
                meaning=meanings.get(era_name),
            )
            for era_name, start_year, end_year in cls.CANONICAL_ERAS
        ]
        return {word.lower(): timeline}
