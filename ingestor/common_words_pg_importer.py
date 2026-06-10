"""
Common Words PostgreSQL Importer.

Adds high-frequency English words to the PostgreSQL words table in ranked tiers.
New rows are intentionally minimal: word + wordfreq metadata only. Existing
enriched rows keep their definitions, etymology, senses, and source fields.

Usage:
    python -m ingestor.common_words_pg_importer --dry-run
    python -m ingestor.common_words_pg_importer --start-rank 1 --limit 5000
    python -m ingestor.common_words_pg_importer --start-rank 5001 --limit 5000
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from typing import Iterable

import psycopg2

from ingestor.base import ImportResult

SYNC_URL: str = os.getenv(
    "POSTGRES_SYNC_URL",
    "postgresql://lexicon:lexicon_secret@localhost:5432/living_lexicon",
)

SOURCE_SLUG = "wordfreq"
PLACEHOLDER_DEFINITION = "Definition pending trusted source import."
_WORD_RE = re.compile(r"^[a-z][a-z']{0,39}$")


@dataclass(frozen=True)
class CommonWordCandidate:
    word: str
    rank: int
    zipf: float


def normalize_candidate(value: str) -> str:
    """Return a lowercase single-word candidate or an empty string if unsafe."""
    word = value.strip().casefold()
    if not _WORD_RE.match(word):
        return ""
    if word.startswith("'") or word.endswith("'"):
        return ""
    return word


def load_common_words(
    *,
    start_rank: int = 1,
    limit: int = 5000,
    min_zipf: float | None = None,
) -> list[CommonWordCandidate]:
    """Load ranked common-word candidates from wordfreq."""
    if start_rank < 1:
        raise ValueError("start_rank must be >= 1")
    if limit < 1:
        raise ValueError("limit must be >= 1")

    try:
        from wordfreq import top_n_list, zipf_frequency
    except ImportError:
        print("[common_words] ERROR: wordfreq not installed. Run: pip install wordfreq", file=sys.stderr)
        sys.exit(1)

    end_rank = start_rank + limit - 1
    raw_words: Iterable[str] = top_n_list("en", end_rank)
    candidates: list[CommonWordCandidate] = []
    seen: set[str] = set()

    for rank, raw_word in enumerate(raw_words, 1):
        if rank < start_rank:
            continue
        word = normalize_candidate(raw_word)
        if not word or word in seen:
            continue
        zipf = float(zipf_frequency(word, "en"))
        if min_zipf is not None and zipf < min_zipf:
            continue
        seen.add(word)
        candidates.append(CommonWordCandidate(word=word, rank=rank, zipf=zipf))

    return candidates


_UPDATE_SQL = """
UPDATE words
SET wordfreq_zipf = %s,
    wordfreq_rank = %s,
    wordfreq_source_slug = %s
WHERE lower(word) = lower(%s)
"""

_INSERT_SQL = """
INSERT INTO words (
    word, entry_type, definition, wordfreq_zipf, wordfreq_rank, wordfreq_source_slug
)
SELECT %s, 'word', %s, %s, %s, %s
WHERE NOT EXISTS (
    SELECT 1 FROM words WHERE lower(word) = lower(%s)
)
"""


def ingest_common_words(
    candidates: list[CommonWordCandidate],
    *,
    dry_run: bool = False,
) -> ImportResult:
    result = ImportResult(dry_run=dry_run)
    if dry_run:
        result.ingested = len(candidates)
        for candidate in candidates[:10]:
            print(
                f"  [dry_run] {candidate.rank:>6} {candidate.word:<20} "
                f"zipf={candidate.zipf:.2f}"
            )
        return result

    conn = psycopg2.connect(SYNC_URL)
    try:
        with conn:
            with conn.cursor() as cur:
                for candidate in candidates:
                    try:
                        cur.execute(
                            _UPDATE_SQL,
                            (candidate.zipf, candidate.rank, SOURCE_SLUG, candidate.word),
                        )
                        if cur.rowcount == 0:
                            cur.execute(
                                _INSERT_SQL,
                                (
                                    candidate.word,
                                    PLACEHOLDER_DEFINITION,
                                    candidate.zipf,
                                    candidate.rank,
                                    SOURCE_SLUG,
                                    candidate.word,
                                ),
                            )
                        result.ingested += 1
                    except Exception as exc:
                        result.failed += 1
                        result.errors.append(f"{candidate.word}: {exc}"[:200])
    finally:
        conn.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Import common English words ranked by wordfreq.")
    parser.add_argument("--start-rank", type=int, default=1, help="First wordfreq rank to import.")
    parser.add_argument("--limit", type=int, default=5000, help="Number of ranked candidates to consider.")
    parser.add_argument("--min-zipf", type=float, default=None, help="Optional minimum Zipf score.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to PostgreSQL.")
    args = parser.parse_args()

    candidates = load_common_words(
        start_rank=args.start_rank,
        limit=args.limit,
        min_zipf=args.min_zipf,
    )
    print(
        f"[common_words] Loaded {len(candidates):,} candidates "
        f"from rank {args.start_rank:,}."
    )
    result = ingest_common_words(candidates, dry_run=args.dry_run)
    print(result.report())
    if not result.ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
