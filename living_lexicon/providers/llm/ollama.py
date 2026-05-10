"""
Ollama LLM provider. Implements LLMProvider protocol.
Extracted from api/ai_engine.py — same model/base_url config, now injectable.
"""
from __future__ import annotations
from langchain_ollama import OllamaLLM

from living_lexicon.config import LexiconConfig


class OllamaProvider:
    """LLMProvider backed by a local Ollama server."""

    def __init__(self, model: str = "llama3", base_url: str = "http://localhost:11434", num_predict: int = 350):
        self._llm = OllamaLLM(model=model, base_url=base_url, num_predict=num_predict)

    @classmethod
    def from_env(cls) -> "OllamaProvider":
        cfg = LexiconConfig()
        return cls(cfg.ollama_model, cfg.ollama_base, cfg.ollama_num_predict)

    def generate(self, prompt: str) -> str:
        return self._llm.invoke(prompt)
