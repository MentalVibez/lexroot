"""
Store providers for the living-lexicon SDK.

    from living_lexicon.providers.stores import HttpStore, Neo4jStore

Neo4jStore requires the neo4j extra:
    pip install living-lexicon[neo4j]

HttpStore is always available (requires only httpx, a core dependency).
"""
from __future__ import annotations

from living_lexicon.providers.stores.http_store import HttpStore

try:
    from living_lexicon.providers.stores.neo4j_store import Neo4jStore
except ImportError:
    Neo4jStore = None  # type: ignore[assignment,misc]

__all__ = ["HttpStore", "Neo4jStore"]
