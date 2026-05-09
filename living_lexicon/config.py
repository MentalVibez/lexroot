"""
Single injectable config object. Replaces the scattered os.getenv() calls
that were spread across graph_client.py, ai_engine.py, and main.py.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field


@dataclass
class LexiconConfig:
    neo4j_uri:      str = field(default_factory=lambda: os.getenv("NEO4J_URI",      "bolt://localhost:7687"))
    neo4j_user:     str = field(default_factory=lambda: os.getenv("NEO4J_USER",     "neo4j"))
    neo4j_password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", "lexicon_secret"))
    ollama_base:    str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    ollama_model:   str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL",   "llama3"))

    def validate_security(self) -> None:
        """Fail closed for unsafe production defaults."""
        env = os.getenv("APP_ENV", "development").lower()
        if env not in {"prod", "production"}:
            return

        _UNSAFE = {"", "lexicon_secret", "password", "neo4j", "secret"}

        if self.neo4j_password in _UNSAFE:
            raise RuntimeError("Refusing to start in production with an unsafe NEO4J_PASSWORD.")

        pg_password = os.getenv("POSTGRES_PASSWORD", "")
        if pg_password in _UNSAFE:
            raise RuntimeError("Refusing to start in production with an unsafe POSTGRES_PASSWORD.")

        if os.getenv("ENABLE_WRITE_ENDPOINTS", "false").lower() == "true" and not os.getenv("ADMIN_API_TOKEN"):
            raise RuntimeError("ENABLE_WRITE_ENDPOINTS=true requires ADMIN_API_TOKEN in production.")

        cors_origins = os.getenv("CORS_ORIGINS", "*")
        if cors_origins.strip() == "*":
            raise RuntimeError("Refusing to start in production with CORS_ORIGINS=* — set explicit origins.")
