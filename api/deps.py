"""
FastAPI dependency injection for the living-lexicon SDK.
Creates a singleton WordHistorian on first call; reused across all requests.
"""
from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from db.database import AsyncSessionLocal
from living_lexicon import WordHistorian
from living_lexicon.providers.llm.ollama import OllamaProvider
from living_lexicon.providers.stores.neo4j_store import Neo4jStore


@lru_cache(maxsize=1)
def get_historian() -> WordHistorian:
    return WordHistorian(
        store=Neo4jStore.from_env(),
        llm=OllamaProvider.from_env(),
    )


async def get_pg_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
