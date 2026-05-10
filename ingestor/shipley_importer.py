"""
Shipley importer — citation-backed root claims from Joseph T. Shipley's
The Origins of English Words.

The book is copyrighted, so this importer expects a small, user-maintained CSV
of factual root mappings and short notes. Do not paste bulk dictionary entries
or long prose from the book into the CSV.

CSV columns:
  word, source_form, source_language, root_meaning, relation_type, confidence,
  page, short_note

Usage:
  python3 -m ingestor.shipley_importer --dry-run
  python3 -m ingestor.shipley_importer --path Words/sources/shipley_roots.csv
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ingestor.base import BaseImporter, ImportResult
from ingestor.graph_loader import EtymologyClaim, LexiconIngestor, WordEntry
from ingestor.sources_catalog import ALL_SOURCES
from ingestor.utils import clean_str as _clean


WORDS_DIR = Path(__file__).parent.parent / "Words"
DEFAULT_PATH = WORDS_DIR / "sources" / "shipley_roots.csv"
SHIPLEY_SOURCE_SLUG = "shipley-1984"


def _register_source(ingestor: LexiconIngestor) -> None:
    for source in ALL_SOURCES:
        if source["slug"] == SHIPLEY_SOURCE_SLUG:
            ingestor.ingest_source(source)
            return
    raise RuntimeError(f"Source '{SHIPLEY_SOURCE_SLUG}' is not in ALL_SOURCES")


def load_shipley_entries(path: str | Path = DEFAULT_PATH) -> list[WordEntry]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Shipley CSV not found: {file_path}")

    entries: list[WordEntry] = []
    seen: set[str] = set()
    with file_path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            word = _clean(row.get("word")).casefold()
            source_form = _clean(row.get("source_form"))
            source_language = _clean(row.get("source_language")) or "Proto-Indo-European"
            root_meaning = _clean(row.get("root_meaning"))
            if not word or not source_form:
                continue
            key = f"{word}|{source_form}|{source_language}"
            if key in seen:
                continue
            seen.add(key)

            page = _clean(row.get("page"))
            short_note = _clean(row.get("short_note"))
            note_parts = [part for part in [root_meaning, f"Shipley p. {page}" if page else "", short_note] if part]
            note = "; ".join(note_parts)
            relation_type = _clean(row.get("relation_type")) or "derived_from"
            confidence = _clean(row.get("confidence")) or "medium"

            entries.append(WordEntry(
                name=word,
                language="English",
                definition="(Shipley root claim; definition supplied by lexical index)",
                root_name=source_form,
                root_meaning=root_meaning or note or "Shipley Indo-European root claim",
                root_origin_language=source_language,
                etymology_claims=[
                    EtymologyClaim(
                        source_form=source_form,
                        source_language=source_language,
                        relation_type=relation_type,
                        source_slug=SHIPLEY_SOURCE_SLUG,
                        confidence=confidence,
                        note=note or "Citation-backed Shipley root claim.",
                        is_reconstructed=source_form.startswith("*") or source_language.startswith("Proto-"),
                    )
                ],
            ))
    return entries


def import_from_shipley(
    path: str | Path = DEFAULT_PATH,
    register_source: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    entries = load_shipley_entries(path)
    print(f"[shipley] Built {len(entries)} root-claim entries from {path}")

    if dry_run:
        for entry in entries[:15]:
            claim = entry.etymology_claims[0] if entry.etymology_claims else None
            print(f"  {entry.name} <- {entry.root_name} ({entry.root_origin_language}) {claim.note if claim else ''}")
        if len(entries) > 15:
            print(f"  ... and {len(entries) - 15} more")
        print("  [dry_run] — no data written")
        return {"entries": len(entries), "dry_run": True}

    ingestor = LexiconIngestor()
    ingestor.ensure_indexes()
    if register_source:
        _register_source(ingestor)

    results = ingestor.bulk_ingest(entries)
    for entry in entries:
        try:
            ingestor.write_attested_in(entry.name, entry.language, SHIPLEY_SOURCE_SLUG)
        except Exception:
            pass
    ingestor.close()

    print(f"[shipley] Done — ingested={results['ingested']}, failed={results['failed']}")
    if results["errors"]:
        for err in results["errors"][:5]:
            print(f"  ERROR: {err['word']}: {err['error']}")
    return results


class ShipleyImporter(BaseImporter):
    """BaseImporter wrapper around import_from_shipley for standard CLI use."""

    default_path = DEFAULT_PATH
    source_name = "shipley"
    cli_description = "Import Shipley root-claim CSV rows into Neo4j."
    extra_cli_args = [
        (["--no-register-source"], {"action": "store_true", "help": "Skip registering Shipley source metadata."}),
    ]

    def load(self, path: Path) -> list[WordEntry]:
        return load_shipley_entries(path)

    def ingest(self, records: list[WordEntry], *, dry_run: bool = False) -> ImportResult:
        result = ImportResult(dry_run=dry_run)
        if dry_run:
            for entry in records[:15]:
                claim = entry.etymology_claims[0] if entry.etymology_claims else None
                print(f"  {entry.name} <- {entry.root_name} ({entry.root_origin_language}) {claim.note if claim else ''}")
            if len(records) > 15:
                print(f"  ... and {len(records) - 15} more")
            result.ingested = len(records)
            return result

        ingestor = LexiconIngestor()
        ingestor.ensure_indexes()
        _register_source(ingestor)
        raw = ingestor.bulk_ingest(records)
        for entry in records:
            try:
                ingestor.write_attested_in(entry.name, entry.language, SHIPLEY_SOURCE_SLUG)
            except Exception:
                pass
        ingestor.close()
        result.ingested = raw.get("ingested", 0)
        result.failed = raw.get("failed", 0)
        result.errors = [f"{e['word']}: {e['error']}" for e in raw.get("errors", [])]
        return result


if __name__ == "__main__":
    ShipleyImporter().run_cli()
