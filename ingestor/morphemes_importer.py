"""Morpheme CSV importer — loads prefix/root/suffix decompositions into PostgreSQL."""
from __future__ import annotations

import csv
from pathlib import Path

import psycopg2
import psycopg2.extras

from ingestor.base import BaseImporter, ImportResult
from ingestor.utils import clean_str, safe_int

_VALID_ROLES = {"prefix", "root", "suffix", "infix"}

_INSERT = """
    INSERT INTO morphemes (word, morpheme, role, origin_language, gloss, position, source_slug)
    VALUES %s
    ON CONFLICT ON CONSTRAINT uq_morphemes
    DO UPDATE SET
        origin_language = EXCLUDED.origin_language,
        gloss           = EXCLUDED.gloss,
        source_slug     = EXCLUDED.source_slug
"""


class MorphemesImporter(BaseImporter):
    source_name = "morphemes-csv"
    cli_description = "Import morpheme decompositions (prefix/root/suffix) from a CSV file."
    default_path = Path("Words/morphemes.csv")

    # Required CSV columns: word, morpheme, role
    # Optional: origin_language, gloss, position, source_slug

    def load(self, path: Path) -> list[dict]:
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def ingest(self, records: list[dict], *, dry_run: bool = False) -> ImportResult:
        result = ImportResult(dry_run=dry_run)
        rows: list[tuple] = []

        for row in records:
            word = clean_str(row.get("word", ""))
            morpheme = clean_str(row.get("morpheme", ""))
            role = clean_str(row.get("role", ""))

            if not word or not morpheme or not role:
                result.skipped += 1
                result.errors.append(f"Missing required field in row: {row}")
                continue

            if role not in _VALID_ROLES:
                result.skipped += 1
                result.errors.append(f"Invalid role '{role}' for morpheme '{morpheme}' in word '{word}'")
                continue

            rows.append((
                word.lower(),
                morpheme.lower(),
                role,
                clean_str(row.get("origin_language", "")),
                clean_str(row.get("gloss", "")),
                safe_int(row.get("position")),
                clean_str(row.get("source_slug", "")),
            ))
            result.ingested += 1

        if dry_run or not rows:
            return result

        import os
        conn = psycopg2.connect(os.environ.get(
            "POSTGRES_SYNC_URL",
            "postgresql://lexicon:lexicon_secret@localhost:5432/living_lexicon",
        ))
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(cur, _INSERT, rows, page_size=500)
            conn.commit()
        finally:
            conn.close()

        return result


if __name__ == "__main__":
    MorphemesImporter().run_cli()
