"""
Apply explicit Neo4j schema migrations for production deployments.

This complements importer idempotence by giving operators one command to run
before ingesting or serving traffic.

Usage:
  python -m ingestor.migrate_schema
"""
from __future__ import annotations

from datetime import datetime, timezone

from ingestor.graph_loader import LexiconIngestor
from ingestor.sources_catalog import ALL_SOURCES


SCHEMA_VERSION = "2026-05-07.1"


def migrate_schema(register_sources: bool = True) -> dict:
    ingestor = LexiconIngestor()
    ingestor.ensure_indexes()

    with ingestor.driver.session() as session:
        session.run(
            """
            CREATE INDEX word_frequency_rank IF NOT EXISTS
            FOR (w:Word) ON (w.frequency_rank)
            """
        )
        session.run(
            """
            CREATE INDEX word_validation_sources IF NOT EXISTS
            FOR (w:Word) ON (w.validation_sources)
            """
        )
        session.run(
            """
            CREATE INDEX etymology_claim_score_fields IF NOT EXISTS
            FOR (c:EtymologyClaim) ON (c.source_language, c.relation_type, c.confidence)
            """
        )
        session.run(
            """
            MERGE (m:SchemaMigration {version: $version})
            SET m.applied_at = $applied_at,
                m.description = $description
            """,
            version=SCHEMA_VERSION,
            applied_at=datetime.now(timezone.utc).isoformat(),
            description="Base constraints/indexes for words, sources, eras, etymology claims, frequency, and validation metadata.",
        )

    source_count = 0
    if register_sources:
        for source in ALL_SOURCES:
            ingestor.ingest_source(source)
            source_count += 1

    ingestor.close()
    return {"schema_version": SCHEMA_VERSION, "sources_registered": source_count}


if __name__ == "__main__":
    result = migrate_schema()
    print(f"[migrate-schema] Applied {result['schema_version']}; sources={result['sources_registered']}")
