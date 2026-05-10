"""Word relations CSV importer — loads semantic and derivational edges into PostgreSQL.

CSV columns (required: from_word, to_word, relation_type):
  from_word, to_word, relation_type, era_name, source_slug, confidence, notes

Valid relation_type values:
  synonym | antonym | hypernym | hyponym | meronym | holonym
  cognate | derived_from | root_of | calque_of | doublet_of

Usage:
  python -m ingestor.word_relations_importer --dry-run
  python -m ingestor.word_relations_importer
  python -m ingestor.word_relations_importer --path Words/sources/word_relations.csv
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

import psycopg2
import psycopg2.extras

from ingestor.base import BaseImporter, ImportResult
from ingestor.utils import clean_str

_VALID_TYPES = {
    "synonym", "antonym", "hypernym", "hyponym", "meronym", "holonym",
    "cognate", "derived_from", "root_of", "calque_of", "doublet_of",
}

_UPSERT = """
    INSERT INTO word_relations (from_word, to_word, relation_type, era_name, source_slug, confidence, notes)
    VALUES %s
    ON CONFLICT ON CONSTRAINT uq_word_relations
    DO UPDATE SET
        era_name   = EXCLUDED.era_name,
        source_slug = EXCLUDED.source_slug,
        confidence = EXCLUDED.confidence,
        notes      = EXCLUDED.notes
"""


class WordRelationsImporter(BaseImporter):
    source_name = "word-relations-csv"
    cli_description = "Import semantic and derivational word relations from a CSV file."
    default_path = Path("Words/sources/word_relations.csv")

    def load(self, path: Path) -> list[dict]:
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def ingest(self, records: list[dict], *, dry_run: bool = False) -> ImportResult:
        result = ImportResult(dry_run=dry_run)
        rows: list[tuple] = []

        for row in records:
            from_word = clean_str(row.get("from_word", ""))
            to_word = clean_str(row.get("to_word", ""))
            relation_type = clean_str(row.get("relation_type", ""))

            if not from_word or not to_word or not relation_type:
                result.skipped += 1
                result.errors.append(f"Missing required field in row: {row}")
                continue

            if relation_type not in _VALID_TYPES:
                result.skipped += 1
                result.errors.append(
                    f"Invalid relation_type '{relation_type}' for {from_word} → {to_word}. "
                    f"Valid: {', '.join(sorted(_VALID_TYPES))}"
                )
                continue

            rows.append((
                from_word.lower(),
                to_word.lower(),
                relation_type,
                clean_str(row.get("era_name", "")) or None,
                clean_str(row.get("source_slug", "")) or None,
                clean_str(row.get("confidence", "")) or "medium",
                clean_str(row.get("notes", "")) or None,
            ))
            result.ingested += 1

        if dry_run or not rows:
            return result

        conn = psycopg2.connect(os.environ.get(
            "POSTGRES_SYNC_URL",
            "postgresql://lexicon:lexicon_secret@localhost:5432/living_lexicon",
        ))
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(cur, _UPSERT, rows, page_size=500)
            conn.commit()
        finally:
            conn.close()

        return result


if __name__ == "__main__":
    WordRelationsImporter().run_cli()
