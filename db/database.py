import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

_DEFAULT_ASYNC = "postgresql+asyncpg://lexicon:lexicon_secret@localhost:5432/living_lexicon"
_DEFAULT_SYNC = "postgresql://lexicon:lexicon_secret@localhost:5432/living_lexicon"

ASYNC_DATABASE_URL: str = os.getenv("POSTGRES_URL", _DEFAULT_ASYNC)
SYNC_DATABASE_URL: str = os.getenv("POSTGRES_SYNC_URL", _DEFAULT_SYNC)

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=int(os.getenv("PG_POOL_SIZE", "10")),
    max_overflow=int(os.getenv("PG_MAX_OVERFLOW", "20")),
    pool_recycle=int(os.getenv("PG_POOL_RECYCLE", "1800")),
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
