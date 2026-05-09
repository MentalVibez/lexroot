"""
Validation word-list importer.

Consumes simple SCOWL/Moby-style word-list files and annotates Word nodes with
validation source tags. This is a quality-control layer, not a definition or
etymology source.

Usage:
  python -m ingestor.wordlist_validator_importer --path Words/scowl.txt --source scowl --dry-run
  python -m ingestor.wordlist_validator_importer --path Words/moby-words.txt --source moby-word-lists --limit 0
"""
from __future__ import annotations

import argparse
import gzip
import re
from pathlib import Path
from typing import Any

from ingestor.graph_loader import LexiconIngestor
from ingestor.sources_catalog import ALL_SOURCES


_WORD = re.compile(r"^[a-z][a-z' -]{1,79}$")


def _open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="ignore")
    return path.open("r", encoding="utf-8", errors="ignore")


def _normalize(value: str) -> str:
    value = value.strip().replace("_", " ").casefold()
    value = re.split(r"[\t,;]", value, maxsplit=1)[0]
    return re.sub(r"\s+", " ", value).strip()


def _is_word(value: str, include_phrases: bool = True) -> bool:
    if not value or value.startswith("#") or not _WORD.match(value):
        return False
    return include_phrases or (" " not in value and "-" not in value)


def load_validation_words(
    path: str | Path,
    limit: int | None = 5000,
    include_phrases: bool = True,
) -> list[str]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Word-list file not found: {file_path}")

    words: list[str] = []
    seen: set[str] = set()
    with _open_text(file_path) as stream:
        for line in stream:
            word = _normalize(line)
            if word in seen or not _is_word(word, include_phrases=include_phrases):
                continue
            seen.add(word)
            words.append(word)
            if limit is not None and len(words) >= limit:
                break
    return words


def _register_source(ingestor: LexiconIngestor, source_slug: str) -> None:
    for source in ALL_SOURCES:
        if source["slug"] == source_slug:
            ingestor.ingest_source(source)
            return
    raise RuntimeError(f"Source '{source_slug}' is not in ALL_SOURCES")


def import_validation_wordlist(
    path: str | Path,
    source_slug: str,
    limit: int | None = 5000,
    include_phrases: bool = True,
    tag: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    print(f"[wordlist] Loading {path} as {source_slug}...")
    words = load_validation_words(path, limit=limit, include_phrases=include_phrases)
    print(f"[wordlist] Parsed {len(words)} validation words")

    if dry_run:
        for word in words[:15]:
            print(f"  {word}")
        print("  [dry_run] — no data written")
        return {"words": len(words), "dry_run": True}

    ingestor = LexiconIngestor()
    ingestor.ensure_indexes()
    _register_source(ingestor, source_slug)
    failed = 0
    for word in words:
        try:
            ingestor.annotate_validation(word, "English", source_slug, tag=tag)
        except Exception:
            failed += 1
    ingestor.close()
    print(f"[wordlist] Done — annotated={len(words) - failed}, failed={failed}")
    return {"annotated": len(words) - failed, "failed": failed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import validation word-list metadata into the Living Lexicon.")
    parser.add_argument("--path", required=True, help="Path to plain text word list, optionally .gz.")
    parser.add_argument("--source", required=True, choices=["scowl", "moby-word-lists"], help="Validation source slug.")
    parser.add_argument("--limit", type=int, default=5000, help="Max words. Use 0 for no limit.")
    parser.add_argument("--single-words-only", action="store_true", help="Skip phrases and hyphenated terms.")
    parser.add_argument("--tag", default="", help="Optional validation tag, such as en_US-large or common.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and preview without writing to Neo4j.")
    args = parser.parse_args()

    import_validation_wordlist(
        path=args.path,
        source_slug=args.source,
        limit=None if args.limit == 0 else args.limit,
        include_phrases=not args.single_words_only,
        tag=args.tag,
        dry_run=args.dry_run,
    )
