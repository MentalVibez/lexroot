"""
One-time idempotent migration: promotes free-text source strings to Source graph nodes.

Safe to run on an existing database. MERGE ensures no duplicates.

Steps:
  1. Create all Source nodes from sources_catalog.ALL_SOURCES
  2. For each HAD_MEANING_IN relationship where h.source is a legacy free-text string:
       - Update h.source to the canonical slug
       - Create an ATTESTED_IN edge from the Word to the Source node

Run: python -m ingestor.migrate_sources
"""
from ingestor.graph_loader import LexiconIngestor
from ingestor.sources_catalog import ALL_SOURCES, LEGACY_SOURCE_MAP


def migrate():
    ingestor = LexiconIngestor()
    ingestor.ensure_indexes()

    print(f"[migrate] Creating {len(ALL_SOURCES)} Source nodes...")
    for source in ALL_SOURCES:
        ingestor.ingest_source(source)
    print("[migrate] Source nodes ready.")

    print(f"[migrate] Migrating {len(LEGACY_SOURCE_MAP)} legacy source string(s)...")
    total_updated = 0

    with ingestor.driver.session() as session:
        for legacy_string, slug in LEGACY_SOURCE_MAP.items():
            result = session.run(
                """
                MATCH (w:Word)-[h:HAD_MEANING_IN]->(e:Era)
                WHERE h.source = $legacy
                SET h.source = $slug
                WITH w
                MATCH (s:Source {slug: $slug})
                MERGE (w)-[:ATTESTED_IN]->(s)
                RETURN count(w) AS updated
                """,
                legacy=legacy_string,
                slug=slug,
            )
            record = result.single()
            count = record["updated"] if record else 0
            if count:
                print(f"  '{legacy_string}' → '{slug}': {count} word(s) updated")
            total_updated += count

    ingestor.close()
    print(f"[migrate] Done — {total_updated} total word-source edges migrated.")


if __name__ == "__main__":
    migrate()
