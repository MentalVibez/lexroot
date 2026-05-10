"""
Neo4j Sync — pushes Word rows from PostgreSQL into the Neo4j graph backend.

Bridges the two storage backends: PostgreSQL holds relational sense/attestation
data; Neo4j holds the graph of etymology trees and cognate relationships that
WordHistorian.context() reads. This script upserts Word nodes and basic
EraTimeline relationships so the SDK reflects ingested content.

Requires the neo4j extra:
    pip install living-lexicon[neo4j]

Usage:
    python -m ingestor.neo4j_sync
    python -m ingestor.neo4j_sync --limit 1000 --dry-run
    python -m ingestor.neo4j_sync --word prevent
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

import psycopg2
import psycopg2.extras

SYNC_URL: str = os.getenv(
    "POSTGRES_SYNC_URL",
    "postgresql://lexicon:lexicon_secret@localhost:5432/living_lexicon",
)

NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "lexicon_neo4j")


@dataclass
class SyncStats:
    words_synced: int = 0
    eras_synced: int = 0
    skipped: int = 0
    failed: int = 0


# ---------------------------------------------------------------------------
# PostgreSQL reader
# ---------------------------------------------------------------------------

_WORD_SQL = """
SELECT
    w.word,
    w.definition,
    w.etymology_root        AS root,
    w.historical_context    AS root_meaning,
    w.origin_language       AS root_origin,
    w.language_family
FROM words w
WHERE (%s IS NULL OR w.word = %s)
ORDER BY w.word
LIMIT %s
"""

_SENSE_SQL = """
SELECT
    s.word,
    s.era_name,
    s.definition            AS meaning,
    s.first_attested_year   AS era_start,
    s.last_attested_year    AS era_end,
    s.example_usage,
    s.source_slug           AS source,
    s.confidence
FROM senses s
WHERE s.word = ANY(%s)
  AND s.era_name IS NOT NULL
ORDER BY s.word, s.first_attested_year
"""


def _fetch_words(conn, word: str | None, limit: int) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        target = word.lower() if word else None
        cur.execute(_WORD_SQL, (target, target, limit))
        return [dict(r) for r in cur.fetchall()]


def _fetch_senses(conn, words: list[str]) -> dict[str, list[dict]]:
    if not words:
        return {}
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(_SENSE_SQL, (words,))
        rows = cur.fetchall()
    out: dict[str, list[dict]] = {w: [] for w in words}
    for row in rows:
        out[row["word"]].append(dict(row))
    return out


# ---------------------------------------------------------------------------
# Neo4j writer
# ---------------------------------------------------------------------------

_WORD_CYPHER = """
MERGE (w:Word {name: $name})
SET
    w.language        = 'English',
    w.definition      = $definition,
    w.root            = $root,
    w.root_meaning    = $root_meaning,
    w.root_origin     = $root_origin,
    w.language_family = $language_family,
    w.synced_at       = datetime()
"""

_ERA_CYPHER = """
MATCH (w:Word {name: $word})
MERGE (e:EraMeaning {word: $word, era_name: $era_name})
SET
    e.meaning       = $meaning,
    e.era_start     = $era_start,
    e.era_end       = $era_end,
    e.usage_example = $usage_example,
    e.source        = $source,
    e.confidence    = $confidence
MERGE (w)-[:HAS_ERA_MEANING]->(e)
"""


def _sync_to_neo4j(
    word_rows: list[dict],
    sense_map: dict[str, list[dict]],
    dry_run: bool,
) -> SyncStats:
    stats = SyncStats()

    if dry_run:
        for row in word_rows[:10]:
            eras = sense_map.get(row["word"], [])
            print(f"  [dry_run] {row['word']!r}  root={row['root']!r}  eras={len(eras)}")
        stats.words_synced = len(word_rows)
        return stats

    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("[neo4j_sync] ERROR: neo4j package not installed. Run: pip install living-lexicon[neo4j]", file=sys.stderr)
        sys.exit(1)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            for row in word_rows:
                word = row["word"]
                try:
                    session.run(
                        _WORD_CYPHER,
                        name=word,
                        definition=row.get("definition"),
                        root=row.get("root"),
                        root_meaning=row.get("root_meaning"),
                        root_origin=row.get("root_origin"),
                        language_family=row.get("language_family"),
                    )
                    stats.words_synced += 1
                except Exception as exc:
                    print(f"  [neo4j_sync] word {word!r} failed: {exc}", file=sys.stderr)
                    stats.failed += 1
                    continue

                for sense in sense_map.get(word, []):
                    try:
                        session.run(
                            _ERA_CYPHER,
                            word=word,
                            era_name=sense["era_name"],
                            meaning=sense.get("meaning"),
                            era_start=sense.get("era_start"),
                            era_end=sense.get("era_end"),
                            usage_example=sense.get("usage_example"),
                            source=sense.get("source"),
                            confidence=sense.get("confidence"),
                        )
                        stats.eras_synced += 1
                    except Exception as exc:
                        print(f"  [neo4j_sync] era {sense['era_name']!r} for {word!r} failed: {exc}", file=sys.stderr)
    finally:
        driver.close()

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--word", help="Sync a single word only.")
    parser.add_argument("--limit", type=int, default=10_000, help="Max words to sync (default 10000; 0 = no limit).")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be synced without writing to Neo4j.")
    args = parser.parse_args()

    limit = args.limit if args.limit > 0 else 10_000_000

    print(f"[neo4j_sync] Connecting to PostgreSQL …")
    pg = psycopg2.connect(SYNC_URL)
    try:
        word_rows = _fetch_words(pg, args.word, limit)
        print(f"[neo4j_sync] {len(word_rows):,} words fetched from PostgreSQL")
        if not word_rows:
            print("[neo4j_sync] Nothing to sync.")
            return

        sense_map = _fetch_senses(pg, [r["word"] for r in word_rows])
        era_total = sum(len(v) for v in sense_map.values())
        print(f"[neo4j_sync] {era_total:,} era senses fetched")
    finally:
        pg.close()

    print(f"[neo4j_sync] {'[DRY RUN] ' if args.dry_run else ''}Syncing to Neo4j …")
    stats = _sync_to_neo4j(word_rows, sense_map, dry_run=args.dry_run)

    print(
        f"[neo4j_sync] Done — words={stats.words_synced:,}  "
        f"eras={stats.eras_synced:,}  failed={stats.failed}"
    )
    if stats.failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
