"""
living-lexicon — Etymology framework for historical word context, semantic drift,
and era-specific meanings. Plug into any Python project or point at a remote server.

Quick start:
    from living_lexicon import WordHistorian

    h = WordHistorian()                          # uses env vars: NEO4J_*, OLLAMA_*
    print(h.context("prevent").root.meaning)     # → "to come before; to precede"
    print(h.explain("charity", context="biblical").ai_explanation)

    # Or connect to a remote instance (no local DB/LLM needed):
    h = WordHistorian.from_url("http://lexicon-service:8000")
"""
from living_lexicon.core import WordHistorian
from living_lexicon.models import (
    DriftExplanation,
    EraContext,
    EraRecord,
    RootInfo,
    SourceInfo,
    WordDetectiveResult,
    WordContext,
)
from living_lexicon.config import LexiconConfig
from living_lexicon.exceptions import (
    EraNotFoundError,
    LexiconError,
    LLMError,
    SourceNotFoundError,
    StoreConnectionError,
    WordNotFoundError,
)
from living_lexicon.testing import InMemoryStore, StubLLMProvider, WordHistorianFactory

__version__ = "0.1.0"

__all__ = [
    "WordHistorian",
    "WordContext",
    "WordDetectiveResult",
    "DriftExplanation",
    "EraContext",
    "EraRecord",
    "RootInfo",
    "SourceInfo",
    "LexiconConfig",
    "LexiconError",
    "WordNotFoundError",
    "EraNotFoundError",
    "SourceNotFoundError",
    "StoreConnectionError",
    "LLMError",
    "InMemoryStore",
    "StubLLMProvider",
    "WordHistorianFactory",
]
