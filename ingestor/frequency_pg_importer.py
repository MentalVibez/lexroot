"""
Frequency PostgreSQL Importer — loads wordfreq Zipf scores into the words table.

Bridges the Neo4j frequency annotations (via frequency_importer.py) with the
PostgreSQL words table, enabling the frequency-blended vitality score and the
/pg/words/trending endpoint.

Requires: pip install wordfreq

Usage:
    python -m ingestor.frequency_pg_importer
    python -m ingestor.frequency_pg_importer --dry-run
    python -m ingestor.frequency_pg_importer --limit 5000
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

from ingestor.base import BaseImporter, ImportResult

SYNC_URL: str = os.getenv(
    "POSTGRES_SYNC_URL",
    "postgresql://lexicon:lexicon_secret@localhost:5432/living_lexicon",
)

SOURCE_SLUG = "wordfreq"


def _load_wordfreq(words: list[str]) -> list[dict[str, Any]]:
    """Return [{word, zipf, rank}] for each word using the wordfreq library."""
    try:
        from wordfreq import word_frequency, zipf_frequency
    except ImportError:
        print("[frequency_pg] ERROR: wordfreq not installed. Run: pip install wordfreq", file=sys.stderr)
        sys.exit(1)

    records = []
    for rank, word in enumerate(words, 1):
        freq = word_frequency(word, "en")
        if freq == 0:
            continue
        zipf = zipf_frequency(word, "en")
        records.append({"word": word, "zipf": zipf, "rank": rank, "freq": freq})
    return records


_UPDATE_SQL = """
UPDATE words
SET wordfreq_zipf = %s, wordfreq_rank = %s, wordfreq_source_slug = %s
WHERE word = %s
"""

_FETCH_WORDS_SQL = "SELECT word FROM words ORDER BY word LIMIT %s OFFSET %s"


class FrequencyPgImporter(BaseImporter):
    source_name = "wordfreq"
    cli_description = "Load wordfreq Zipf scores into the PostgreSQL words table."
    default_path = None  # reads from the DB itself, no input file

    def load(self, path: Path | None = None) -> list[Any]:
        """Fetch all word strings from PostgreSQL."""
        conn = psycopg2.connect(SYNC_URL)
        try:
            words: list[str] = []
            offset = 0
            batch = 10_000
            with conn.cursor() as cur:
                while True:
                    cur.execute(_FETCH_WORDS_SQL, (batch, offset))
                    rows = cur.fetchall()
                    if not rows:
                        break
                    words.extend(r[0] for r in rows)
                    offset += batch
            print(f"[frequency_pg] {len(words):,} words fetched from PostgreSQL")
            return words
        finally:
            conn.close()

    def ingest(self, records: list[Any], *, dry_run: bool = False) -> ImportResult:
        result = ImportResult(dry_run=dry_run)
        freq_records = _load_wordfreq(records)
        print(f"[frequency_pg] {len(freq_records):,} words have wordfreq data")

        if dry_run:
            for r in freq_records[:10]:
                print(f"  [dry_run] {r['word']!r:<25} zipf={r['zipf']:.2f}  rank={r['rank']:,}")
            result.ingested = len(freq_records)
            result.skipped = len(records) - len(freq_records)
            return result

        conn = psycopg2.connect(SYNC_URL)
        try:
            with conn:
                with conn.cursor() as cur:
                    batch_data = [
                        (r["zipf"], r["rank"], SOURCE_SLUG, r["word"])
                        for r in freq_records
                    ]
                    psycopg2.extras.execute_batch(cur, _UPDATE_SQL, batch_data, page_size=1000)
                    result.ingested = len(batch_data)
                    result.skipped = len(records) - len(batch_data)
        finally:
            conn.close()

        return result

    def run_cli(self) -> None:
        """Override to skip --path arg since we read from the DB."""
        import argparse
        parser = argparse.ArgumentParser(description=self.cli_description)
        parser.add_argument("--limit", type=int, default=0, help="Max words (0 = all)")
        parser.add_argument("--dry-run", action="store_true")
        args = parser.parse_args()

        words = self.load()
        if args.limit:
            words = words[: args.limit]
        result = self.ingest(words, dry_run=args.dry_run)
        print(result.report())
        if not result.ok:
            sys.exit(1)


if __name__ == "__main__":
    FrequencyPgImporter().run_cli()
