import os
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

_DEFAULT_ASYNC = "postgresql+asyncpg://lexicon:lexicon_secret@localhost:5432/living_lexicon"
_DEFAULT_SYNC = "postgresql://lexicon:lexicon_secret@localhost:5432/living_lexicon"


def _normalize_postgres_url(url: str, async_driver: bool) -> str:
    """Return a SQLAlchemy-compatible PostgreSQL URL for async or sync clients."""
    parts = urlsplit(url)
    scheme = parts.scheme
    if scheme == "postgres":
        scheme = "postgresql"
    if async_driver:
        if scheme in {"postgresql", "postgresql+psycopg2"}:
            scheme = "postgresql+asyncpg"
    elif scheme == "postgresql+asyncpg":
        scheme = "postgresql"
    return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))


_RENDER_OR_GENERIC_DATABASE_URL = os.getenv("DATABASE_URL", "")

ASYNC_DATABASE_URL: str = _normalize_postgres_url(
    os.getenv("POSTGRES_URL") or _RENDER_OR_GENERIC_DATABASE_URL or _DEFAULT_ASYNC,
    async_driver=True,
)
SYNC_DATABASE_URL: str = _normalize_postgres_url(
    os.getenv("POSTGRES_SYNC_URL") or _RENDER_OR_GENERIC_DATABASE_URL or _DEFAULT_SYNC,
    async_driver=False,
)

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
