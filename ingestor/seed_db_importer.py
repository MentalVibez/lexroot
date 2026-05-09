"""
Etymology Seed Database Importer — loads seed data from Words/etymology_seed_database.csv files.

The seed databases contain foundational words with their historical origins and contexts.
Format:
  word, origin_language, language_family, historical_context

Usage:
  python -m ingestor.seed_db_importer --path Words/etymology_seed_database.csv
  python -m ingestor.seed_db_importer --path Words/etymology_seed_database_v2.csv
  python -m ingestor.seed_db_importer --path-all  # Import both
"""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Any

from ingestor.graph_loader import LexiconIngestor, WordEntry

SEED_DB_SOURCE = {
    "slug": "etymology-seed-database",
    "short_name": "Etymology Seed Database",
    "full_name": "Etymology Seed Database",
    "author": "Living Lexicon Project",
    "year": 2026,
    "publisher": "Living Lexicon Project",
    "category": "seed-data",
    "authority_tier": 3,
    "description": "Foundational etymological seed data with historical contexts.",
}

WORDS_DIR = Path(__file__).parent.parent / "Words"
SEED_DATABASE_V1 = WORDS_DIR / "etymology_seed_database.csv"
SEED_DATABASE_V2 = WORDS_DIR / "etymology_seed_database_v2.csv"


def load_seed_db_records(path: str) -> list[dict[str, Any]]:
    """Load records from a seed database CSV file."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Seed database file not found: {path}")

    records = []
    with file_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("word"):
                records.append(row)
    return records


def build_seed_db_word_entries(records: list[dict[str, Any]]) -> list[WordEntry]:
    """Convert seed database records into WordEntry objects."""
    entries = []
    seen_words = set()

    for record in records:
        word = record.get("word", "").strip()
        if not word or word in seen_words:
            continue
        seen_words.add(word)

        origin_lang = record.get("origin_language", "").strip() or "Unknown"
        language_family = record.get("language_family", "").strip() or "Unknown"
        historical_context = record.get("historical_context", "").strip()

        definition = f"({historical_context})" if historical_context else f"Seed word from {origin_lang}"

        entries.append(WordEntry(
            name=word,
            language="English",
            definition=definition,
            root_name=word,
            root_meaning=historical_context or f"Seed data: {origin_lang}",
            root_origin_language=origin_lang,
            attested_year=None,
            cognates=None,
            era_meanings=[
                {
                    "era_name": "Modern English",
                    "meaning": historical_context or f"Seed: {origin_lang}",
                    "usage_example": None,
                    "register": "general",
                    "source": SEED_DB_SOURCE["slug"],
                    "confidence": "medium",
                }
            ] if historical_context else None,
        ))

    return entries


def import_from_seed_db(
    paths: list[str] | None = None,
    register_source: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Import seed database records and ingest them into Neo4j.

    Args:
        paths: list of file paths to import (default: both seed database versions)
        register_source: register the source node before ingestion
        dry_run: parse and preview without writing to Neo4j
    """
    if paths is None:
        paths = [str(SEED_DATABASE_V1), str(SEED_DATABASE_V2)]

    all_records: list[dict[str, Any]] = []
    for path in paths:
        print(f"[seed-db] Loading {path}…")
        records = load_seed_db_records(path)
        print(f"[seed-db] Parsed {len(records)} records from {path}")
        all_records.extend(records)

    entries = build_seed_db_word_entries(all_records)
    print(f"[seed-db] Built {len(entries)} unique WordEntry objects")

    if dry_run:
        for entry in entries[:15]:
            print(f"  {entry.name} | origin={entry.root_origin_language}")
        if len(entries) > 15:
            print(f"  … and {len(entries) - 15} more")
        print("  [dry_run] — no data written")
        return {"entries": len(entries), "dry_run": True}

    ingestor = LexiconIngestor()
    ingestor.ensure_indexes()
    if register_source:
        print(f"[seed-db] Registering source {SEED_DB_SOURCE['slug']}")
        ingestor.ingest_source(SEED_DB_SOURCE)

    results = ingestor.bulk_ingest(entries)
    ingestor.close()

    print(f"[seed-db] Done — ingested={results['ingested']}, failed={results['failed']}")
    if results["errors"]:
        for err in results["errors"][:5]:
            print(f"  ERROR: {err['word']}: {err['error']}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import etymology seed database records into the Living Lexicon."
    )
    parser.add_argument(
        "--path",
        nargs="+",
        help="Path(s) to seed database CSV file(s).",
    )
    parser.add_argument(
        "--path-all",
        action="store_true",
        help="Import all available seed database files.",
    )
    parser.add_argument(
        "--no-register-source",
        action="store_true",
        help="Do not register the seed database source node before ingesting.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and preview entries without writing to Neo4j.",
    )
    args = parser.parse_args()

    paths = None
    if args.path:
        paths = args.path
    elif args.path_all:
        paths = [str(SEED_DATABASE_V1), str(SEED_DATABASE_V2)]

    import_from_seed_db(
        paths=paths,
        register_source=not args.no_register_source,
        dry_run=args.dry_run,
    )
