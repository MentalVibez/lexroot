"""
Princeton WordNet importer for broad English headword coverage.

The bundled Words/wordnet.dat file is a UWN plugin export. This importer extracts
English lexical terms from that local file and creates lightweight Word entries.
It deliberately treats WordNet as modern lexical coverage, not as an etymology
authority; EtymWordNet and scholarly sources enrich roots and history later.

Usage:
  python -m ingestor.wordnet_importer --limit 1000 --dry-run
  python -m ingestor.wordnet_importer --limit 0
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

try:
    import nltk
    from nltk.corpus import wordnet as wn
    _NLTK_AVAILABLE = True
except ImportError:
    _NLTK_AVAILABLE = False

from ingestor.graph_loader import LexiconIngestor, WordEntry
from ingestor.sources_catalog import ALL_SOURCES


WORDS_DIR = Path(__file__).parent.parent / "Words"
WORDNET_PATH = WORDS_DIR / "wordnet.dat"
WORDNET_SOURCE_SLUG = "princeton-wordnet"

_TERM_PATTERN = re.compile(rb"(?<![A-Za-z+])t/eng/([^?\x00-\x1f]{1,120})\?")
_SIMPLE_TERM = re.compile(r"^[a-z][a-z' -]{1,79}$")
_DEFINITION_LIKE_WORDS = {
    "consisting",
    "especially",
    "formerly",
    "having",
    "someone",
    "something",
    "usually",
    "whether",
    "which",
    "whose",
}


def _normalize_term(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="ignore")
    text = text.replace("_", " ").strip().casefold()
    text = re.sub(r"\s+", " ", text)
    return text


def _is_seedable_term(term: str, include_phrases: bool = True) -> bool:
    if not term or not _SIMPLE_TERM.match(term):
        return False
    words = term.split()
    if not include_phrases and (" " in term or "-" in term):
        return False
    if include_phrases and len(words) > 5:
        return False
    if any(word in _DEFINITION_LIKE_WORDS for word in words):
        return False
    if words[0] in {"a", "an", "the"} and len(words) > 3:
        return False
    return True


def _get_definition(term: str) -> str:
    if not _NLTK_AVAILABLE:
        return ""
    try:
        synsets = wn.synsets(term.replace(" ", "_"), lang="eng")
    except LookupError:
        return ""
    if synsets:
        return synsets[0].definition()
    return ""


def _ensure_nltk(download: bool = False) -> None:
    if not _NLTK_AVAILABLE:
        print("[wordnet] nltk not installed — definitions will be placeholders.")
        return
    try:
        wn.synsets("test")
    except LookupError:
        if download:
            print("[wordnet] Downloading NLTK WordNet corpus...")
            nltk.download("wordnet", quiet=True)
            nltk.download("omw-1.4", quiet=True)
        else:
            print("[wordnet] NLTK WordNet corpus unavailable — definitions will be placeholders.")


def load_wordnet_terms(
    path: str | Path = WORDNET_PATH,
    limit: int | None = None,
    include_phrases: bool = True,
) -> list[str]:
    """Extract unique normalized English terms from the local UWN WordNet plugin file."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"WordNet data file not found: {file_path}")

    terms: list[str] = []
    seen: set[str] = set()
    data = file_path.read_bytes()
    for match in _TERM_PATTERN.finditer(data):
        term = _normalize_term(match.group(1))
        if term in seen or not _is_seedable_term(term, include_phrases=include_phrases):
            continue
        seen.add(term)
        terms.append(term)
        if limit is not None and len(terms) >= limit:
            break
    return terms


def build_wordnet_entries(
    terms: list[str],
    include_definitions: bool = True,
) -> list[WordEntry]:
    """Convert WordNet terms into lightweight, source-cited WordEntry objects."""
    if include_definitions:
        _ensure_nltk(download=False)

    entries: list[WordEntry] = []
    for term in terms:
        definition = _get_definition(term) if include_definitions else ""
        if not definition:
            definition = f"(Princeton WordNet lexical item; definition pending enrichment)"

        entries.append(WordEntry(
            name=term,
            language="English",
            definition=definition,
            root_name=term,
            root_meaning="WordNet lexical headword; etymology pending enrichment",
            root_origin_language="Modern English",
            attested_year=None,
            cognates=None,
            era_meanings=[
                {
                    "era_name": "Modern English",
                    "meaning": definition,
                    "usage_example": None,
                    "register": "general",
                    "source": WORDNET_SOURCE_SLUG,
                    "confidence": "medium",
                }
            ],
        ))
    return entries


def _register_wordnet_source(ingestor: LexiconIngestor) -> None:
    for source in ALL_SOURCES:
        if source["slug"] == WORDNET_SOURCE_SLUG:
            ingestor.ingest_source(source)
            return
    raise RuntimeError(f"Source '{WORDNET_SOURCE_SLUG}' is not in ALL_SOURCES")


def import_from_wordnet(
    path: str | Path = WORDNET_PATH,
    limit: int | None = 5000,
    include_phrases: bool = True,
    include_definitions: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    print(f"[wordnet] Loading terms from {path}...")
    terms = load_wordnet_terms(path, limit=limit, include_phrases=include_phrases)
    print(f"[wordnet] Built {len(terms)} unique normalized terms")

    entries = build_wordnet_entries(terms, include_definitions=include_definitions)

    if dry_run:
        for entry in entries[:15]:
            print(f"  {entry.name} | def={entry.definition[:70]}")
        if len(entries) > 15:
            print(f"  ... and {len(entries) - 15} more")
        print("  [dry_run] — no data written")
        return {"entries": len(entries), "dry_run": True}

    ingestor = LexiconIngestor()
    ingestor.ensure_indexes()
    _register_wordnet_source(ingestor)

    results = ingestor.bulk_ingest(entries)
    for entry in entries:
        try:
            ingestor.write_attested_in(entry.name, entry.language, WORDNET_SOURCE_SLUG)
        except Exception:
            pass
    ingestor.close()

    print(f"[wordnet] Done — ingested={results['ingested']}, failed={results['failed']}")
    if results["errors"]:
        for err in results["errors"][:5]:
            print(f"  ERROR: {err['word']}: {err['error']}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Princeton WordNet headwords into the Living Lexicon.")
    parser.add_argument("--path", default=str(WORDNET_PATH), help="Path to Words/wordnet.dat")
    parser.add_argument("--limit", type=int, default=5000, help="Max terms to import. Use 0 for no limit.")
    parser.add_argument("--single-words-only", action="store_true", help="Skip multi-word and hyphenated terms.")
    parser.add_argument("--no-definitions", action="store_true", help="Do not try to enrich terms from NLTK WordNet.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and preview without writing to Neo4j.")
    args = parser.parse_args()

    import_from_wordnet(
        path=args.path,
        limit=None if args.limit == 0 else args.limit,
        include_phrases=not args.single_words_only,
        include_definitions=not args.no_definitions,
        dry_run=args.dry_run,
    )
