"""
FastAPI dependency injection for the living-lexicon SDK.
Creates a singleton WordHistorian on first call; reused across all requests.
"""
from collections.abc import AsyncGenerator
from functools import lru_cache
import os

from sqlalchemy.ext.asyncio import AsyncSession

from db.database import AsyncSessionLocal
from living_lexicon import WordHistorian
from fastapi import HTTPException

from living_lexicon.exceptions import LLMError, SourceNotFoundError, WordNotFoundError


class DisabledLexiconStore:
    """Store stub used when the legacy Neo4j-backed SDK routes are disabled."""

    def ping(self) -> bool:
        return True

    def get_word(self, word: str):
        raise WordNotFoundError(word)

    def get_word_tree(self, word: str):
        return {}

    def get_cognates(self, word: str):
        return []

    def get_etymology_claims(self, word: str):
        return []

    def search(self, query: str, limit: int = 10):
        return []

    def get_word_era_meanings(self, word: str):
        return []

    def get_era_timeline(self, word: str):
        return []

    def get_word_in_era(self, word: str, era_name: str):
        return None

    def get_era_by_year(self, year: int):
        return None

    def get_words_by_era(self, era_name: str, limit: int = 20):
        return []

    def get_word_sources(self, word: str):
        return []

    def get_all_sources(self):
        return []

    def get_source(self, slug: str):
        raise SourceNotFoundError(slug)

    def get_words_by_source(self, slug: str, limit: int = 20):
        return []


class DisabledLLMProvider:
    def generate(self, prompt: str) -> str:
        raise LLMError("LLM provider is disabled for this deployment.")


@lru_cache(maxsize=1)
def get_historian() -> WordHistorian:
    if os.getenv("ENABLE_NEO4J", "true").lower() == "false":
        llm = None if os.getenv("ENABLE_OLLAMA", "true").lower() == "false" else DisabledLLMProvider()
        return WordHistorian(store=DisabledLexiconStore(), llm=llm)

    from living_lexicon.providers.llm.ollama import OllamaProvider
    from living_lexicon.providers.stores.neo4j_store import Neo4jStore
    llm = None
    if os.getenv("ENABLE_OLLAMA", "true").lower() == "true":
        llm = OllamaProvider.from_env()
    return WordHistorian(
        store=Neo4jStore.from_env(),
        llm=llm,
    )


def legacy_sdk_enabled() -> bool:
    return os.getenv("ENABLE_NEO4J", "true").lower() == "true"


def require_legacy_sdk() -> None:
    if not legacy_sdk_enabled():
        raise HTTPException(
            status_code=503,
            detail="Legacy graph-backed routes are disabled on this deployment. Use /pg/* endpoints.",
        )


async def get_pg_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
