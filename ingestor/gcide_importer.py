"""
GCIDE importer.

Consumes local GCIDE tagged text/XML files and imports English headwords with
historical dictionary definitions. GCIDE is useful as a broad historical
definition layer; etymology-specific roots are kept pending unless a source
entry exposes clear etymology text.

Usage:
  python -m ingestor.gcide_importer --path Words/gcide.xml --limit 1000 --dry-run
  python -m ingestor.gcide_importer --path Words/gcide.txt --limit 0
"""
from __future__ import annotations

import argparse
import re
from html import unescape
from pathlib import Path
from typing import Any

from ingestor.graph_loader import LexiconIngestor, WordEntry
from ingestor.sources_catalog import ALL_SOURCES


GCIDE_SOURCE_SLUG = "gcide"
_ENTRY_PATTERN = re.compile(r"<ent>(?P<word>.*?)</ent>(?P<body>.*?)(?=<ent>|$)", re.I | re.S)
_DEF_PATTERN = re.compile(r"<def>(?P<definition>.*?)</def>", re.I | re.S)
_TAG_PATTERN = re.compile(r"<[^>]+>")
_WORD = re.compile(r"^[a-z][a-z' -]{1,79}$")


def _clean_text(value: str) -> str:
    value = _TAG_PATTERN.sub(" ", value)
    value = unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _normalize_word(value: str) -> str:
    value = _clean_text(value).casefold()
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _is_seedable(word: str, include_phrases: bool = True) -> bool:
    if not word or not _WORD.match(word):
        return False
    return include_phrases or (" " not in word and "-" not in word)


def load_gcide_entries(
    path: str | Path,
    limit: int | None = 5000,
    include_phrases: bool = True,
) -> list[WordEntry]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"GCIDE file not found: {file_path}")

    text = file_path.read_text(encoding="utf-8", errors="ignore")
    entries: list[WordEntry] = []
    seen: set[str] = set()

    for match in _ENTRY_PATTERN.finditer(text):
        word = _normalize_word(match.group("word"))
        if word in seen or not _is_seedable(word, include_phrases=include_phrases):
            continue
        body = match.group("body")
        definition_match = _DEF_PATTERN.search(body)
        if not definition_match:
            continue
        definition = _clean_text(definition_match.group("definition"))
        if not definition:
            continue

        seen.add(word)
        entries.append(WordEntry(
            name=word,
            language="English",
            definition=definition[:1000],
            root_name=word,
            root_meaning="GCIDE historical dictionary entry; etymology pending enrichment",
            root_origin_language="Modern English",
            cognates=None,
            era_meanings=[
                {
                    "era_name": "18th-19th Century English",
                    "meaning": definition[:1000],
                    "usage_example": None,
                    "register": "general",
                    "source": GCIDE_SOURCE_SLUG,
                    "confidence": "medium",
                }
            ],
        ))
        if limit is not None and len(entries) >= limit:
            break
    return entries


def _register_source(ingestor: LexiconIngestor) -> None:
    for source in ALL_SOURCES:
        if source["slug"] == GCIDE_SOURCE_SLUG:
            ingestor.ingest_source(source)
            return
    raise RuntimeError(f"Source '{GCIDE_SOURCE_SLUG}' is not in ALL_SOURCES")


def import_from_gcide(
    path: str | Path,
    limit: int | None = 5000,
    include_phrases: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    print(f"[gcide] Loading {path}...")
    entries = load_gcide_entries(path, limit=limit, include_phrases=include_phrases)
    print(f"[gcide] Built {len(entries)} WordEntry objects")

    if dry_run:
        for entry in entries[:10]:
            print(f"  {entry.name} | def={entry.definition[:70]}")
        print("  [dry_run] — no data written")
        return {"entries": len(entries), "dry_run": True}

    ingestor = LexiconIngestor()
    ingestor.ensure_indexes()
    _register_source(ingestor)
    results = ingestor.bulk_ingest(entries)
    for entry in entries:
        try:
            ingestor.write_attested_in(entry.name, entry.language, GCIDE_SOURCE_SLUG)
        except Exception:
            pass
    ingestor.close()
    print(f"[gcide] Done — ingested={results['ingested']}, failed={results['failed']}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import GCIDE tagged text/XML data into the Living Lexicon.")
    parser.add_argument("--path", required=True, help="Path to GCIDE tagged text/XML file.")
    parser.add_argument("--limit", type=int, default=5000, help="Max entries. Use 0 for no limit.")
    parser.add_argument("--single-words-only", action="store_true", help="Skip phrases and hyphenated terms.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and preview without writing to Neo4j.")
    args = parser.parse_args()

    import_from_gcide(
        path=args.path,
        limit=None if args.limit == 0 else args.limit,
        include_phrases=not args.single_words_only,
        dry_run=args.dry_run,
    )
