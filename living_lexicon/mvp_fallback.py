"""Small read-only fallback dataset for MVP/demo availability.

The production source of truth remains PostgreSQL. These records keep the public
Word Explorer useful when a local/dev database is unavailable or not seeded yet.
"""
from __future__ import annotations

from copy import deepcopy


FEATURED_WORDS: dict[str, dict] = {
    "awful": {
        "id": -1,
        "word": "awful",
        "entry_type": "word",
        "phonemes": None,
        "etymology_root": "awe",
        "definition": "Extremely bad or unpleasant.",
        "definition_source_slug": "oed-2e",
        "definition_source_name": "Oxford English Dictionary",
        "definition_license": "citation lead; verify against licensed source",
        "origin_language": "Old English",
        "language_family": "Germanic",
        "historical_context": "Earlier senses centered on awe, dread, or reverence before the word drifted toward strong negative judgment.",
        "literal_meaning": "Full of awe.",
        "figurative_meaning": "Very bad; terrible.",
        "example_usage": "The weather was awful.",
        "semantic_drift_history": [
            {
                "era_name": "Old English / Middle English",
                "meaning": "Inspiring awe, dread, or reverence.",
                "start_year": 1000,
                "end_year": 1500,
                "source_slug": "oed-2e",
                "confidence": "medium",
                "evidence_grade": "C",
                "semantic_change_type": "pejoration",
            },
            {
                "era_name": "Modern English",
                "meaning": "Very bad, unpleasant, or intense.",
                "start_year": 1800,
                "end_year": 2026,
                "source_slug": "merriam-webster",
                "confidence": "medium",
                "evidence_grade": "C",
                "semantic_change_type": "pejoration",
            },
        ],
    },
    "nice": {
        "id": -2,
        "word": "nice",
        "entry_type": "word",
        "phonemes": None,
        "etymology_root": "nescius",
        "definition": "Pleasant, agreeable, or kind.",
        "definition_source_slug": "oed-2e",
        "definition_source_name": "Oxford English Dictionary",
        "definition_license": "citation lead; verify against licensed source",
        "origin_language": "Latin via Old French",
        "language_family": "Indo-European",
        "historical_context": "From Latin nescius, not knowing; the English word moved through several social meanings before becoming positive.",
        "literal_meaning": "Not knowing.",
        "figurative_meaning": "Pleasant or agreeable.",
        "example_usage": "That was a nice thing to say.",
        "semantic_drift_history": [
            {
                "era_name": "Middle English",
                "meaning": "Foolish, ignorant, or wanton.",
                "start_year": 1300,
                "end_year": 1500,
                "source_slug": "mec-corpus",
                "confidence": "medium",
                "evidence_grade": "C",
                "semantic_change_type": "amelioration",
            },
            {
                "era_name": "Modern English",
                "meaning": "Pleasant, agreeable, kind, or socially acceptable.",
                "start_year": 1800,
                "end_year": 2026,
                "source_slug": "merriam-webster",
                "confidence": "medium",
                "evidence_grade": "C",
                "semantic_change_type": "amelioration",
            },
        ],
    },
    "lord": {
        "id": -3,
        "word": "lord",
        "entry_type": "word",
        "phonemes": None,
        "etymology_root": "hlaford",
        "definition": "A ruler, noble, master, or divine title.",
        "definition_source_slug": "bosworth-toller",
        "definition_source_name": "Bosworth-Toller Anglo-Saxon Dictionary",
        "definition_license": "public-domain dictionary; verify exact citation",
        "origin_language": "Old English",
        "language_family": "Germanic",
        "historical_context": "Old English hlaford is traditionally explained as loaf-guardian, tying authority to household provision.",
        "literal_meaning": "Loaf-guardian.",
        "figurative_meaning": "A person with authority or rank.",
        "example_usage": "The lord held land and owed duties.",
        "semantic_drift_history": [
            {
                "era_name": "Old English",
                "meaning": "Household head or guardian of bread/provision.",
                "start_year": 900,
                "end_year": 1150,
                "source_slug": "bosworth-toller",
                "confidence": "medium",
                "evidence_grade": "C",
                "semantic_change_type": "specialization",
            },
            {
                "era_name": "Modern English",
                "meaning": "Noble title, master, or divine address.",
                "start_year": 1500,
                "end_year": 2026,
                "source_slug": "oed-2e",
                "confidence": "medium",
                "evidence_grade": "C",
                "semantic_change_type": "specialization",
            },
        ],
    },
    "silly": {
        "id": -4,
        "word": "silly",
        "entry_type": "word",
        "phonemes": None,
        "etymology_root": "saelig",
        "definition": "Showing a lack of good sense; foolish or trivial.",
        "definition_source_slug": "oed-2e",
        "definition_source_name": "Oxford English Dictionary",
        "definition_license": "citation lead; verify against licensed source",
        "origin_language": "Old English",
        "language_family": "Germanic",
        "historical_context": "Old English saelig meant blessed or happy; later senses moved through innocence and simplicity toward foolishness.",
        "literal_meaning": "Blessed or happy.",
        "figurative_meaning": "Foolish or lacking judgment.",
        "example_usage": "That was a silly mistake.",
        "semantic_drift_history": [
            {
                "era_name": "Old English",
                "meaning": "Blessed, happy, fortunate.",
                "start_year": 900,
                "end_year": 1150,
                "source_slug": "oed-2e",
                "confidence": "medium",
                "evidence_grade": "C",
                "semantic_change_type": "pejoration",
            },
            {
                "era_name": "Modern English",
                "meaning": "Foolish, trivial, or lacking good sense.",
                "start_year": 1700,
                "end_year": 2026,
                "source_slug": "merriam-webster",
                "confidence": "medium",
                "evidence_grade": "C",
                "semantic_change_type": "pejoration",
            },
        ],
    },
    "prevent": {
        "id": -5,
        "word": "prevent",
        "entry_type": "word",
        "phonemes": None,
        "etymology_root": "praevenire",
        "definition": "To stop something from happening.",
        "definition_source_slug": "oed-2e",
        "definition_source_name": "Oxford English Dictionary",
        "definition_license": "citation lead; verify against licensed source",
        "origin_language": "Latin via French",
        "language_family": "Indo-European",
        "historical_context": "Latin praevenire means to come before; older English could preserve the sense of preceding or anticipating.",
        "literal_meaning": "To come before.",
        "figurative_meaning": "To stop or hinder.",
        "example_usage": "Rules prevent confusion.",
        "semantic_drift_history": [
            {
                "era_name": "Early Modern English",
                "meaning": "To come before, anticipate, or precede.",
                "start_year": 1500,
                "end_year": 1700,
                "source_slug": "oed-2e",
                "confidence": "medium",
                "evidence_grade": "C",
                "semantic_change_type": "narrowing",
            },
            {
                "era_name": "Modern English",
                "meaning": "To stop, hinder, or keep from happening.",
                "start_year": 1800,
                "end_year": 2026,
                "source_slug": "merriam-webster",
                "confidence": "medium",
                "evidence_grade": "C",
                "semantic_change_type": "specialization",
            },
        ],
    },
    "charity": {
        "id": -6,
        "word": "charity",
        "entry_type": "word",
        "phonemes": None,
        "etymology_root": "caritas",
        "definition": "Generous help for people in need.",
        "definition_source_slug": "oed-2e",
        "definition_source_name": "Oxford English Dictionary",
        "definition_license": "citation lead; verify against licensed source",
        "origin_language": "Latin via Old French",
        "language_family": "Indo-European",
        "historical_context": "Latin caritas carried senses of dearness, love, and Christian love before modern English narrowed toward benevolent giving.",
        "literal_meaning": "Dearness or love.",
        "figurative_meaning": "Organized giving or benevolence.",
        "example_usage": "The charity supports local families.",
        "semantic_drift_history": [
            {
                "era_name": "Middle English",
                "meaning": "Christian love, benevolence, or selfless love.",
                "start_year": 1200,
                "end_year": 1500,
                "source_slug": "mec-corpus",
                "confidence": "medium",
                "evidence_grade": "C",
                "semantic_change_type": "narrowing",
            },
            {
                "era_name": "Modern English",
                "meaning": "Generous giving or an organization that gives aid.",
                "start_year": 1800,
                "end_year": 2026,
                "source_slug": "merriam-webster",
                "confidence": "medium",
                "evidence_grade": "C",
                "semantic_change_type": "narrowing",
            },
        ],
    },
}


def get_featured_word(word: str) -> dict | None:
    record = FEATURED_WORDS.get(word.casefold())
    return deepcopy(record) if record else None


def search_featured_words(prefix: str, limit: int = 20) -> list[dict]:
    folded = prefix.casefold()
    matches = [
        deepcopy(record)
        for key, record in sorted(FEATURED_WORDS.items())
        if key.startswith(folded)
    ]
    return matches[:limit]


def era_check_featured_words(text: str, era_name: str) -> list[dict]:
    tokens = set()
    for raw in text.split():
        token = raw.strip(".,;:!?()[]{}\"'").casefold()
        if not token:
            continue
        tokens.add(token)
        if token.endswith("ing") and len(token) > 5:
            tokens.add(token[:-3])
        if token.endswith("ed") and len(token) > 4:
            tokens.add(token[:-2])
            tokens.add(token[:-1])
        if token.endswith("s") and len(token) > 3:
            tokens.add(token[:-1])
    flagged: list[dict] = []
    for word in sorted(tokens):
        record = FEATURED_WORDS.get(word)
        if not record:
            continue
        for sense in record.get("semantic_drift_history") or []:
            if sense.get("era_name") == era_name:
                flagged.append(
                    {
                        "word": record["word"],
                        "era_definition": sense["meaning"],
                        "era_source": sense.get("source_slug"),
                        "modern_definition": record.get("definition"),
                        "part_of_speech": None,
                    }
                )
                break
    return flagged
