"""
LLM providers for the living-lexicon SDK.

    from living_lexicon.providers.llm import OllamaProvider

OllamaProvider requires the ollama extra:
    pip install living-lexicon[ollama]
"""
from __future__ import annotations

try:
    from living_lexicon.providers.llm.ollama import OllamaProvider
except ImportError:
    OllamaProvider = None  # type: ignore[assignment,misc]

__all__ = ["OllamaProvider"]
