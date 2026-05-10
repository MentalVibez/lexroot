"""
Provider implementations for the living-lexicon SDK.

    from living_lexicon.providers import HttpStore, Neo4jStore, OllamaProvider

Optional providers return None when their extras are not installed.
Check before use: if Neo4jStore is not None: ...
"""
from __future__ import annotations

from living_lexicon.providers.stores import HttpStore, Neo4jStore
from living_lexicon.providers.llm import OllamaProvider

__all__ = ["HttpStore", "Neo4jStore", "OllamaProvider"]
