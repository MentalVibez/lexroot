from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Word


async def get_word(session: AsyncSession, word: str) -> Word | None:
    result = await session.execute(select(Word).where(Word.word == word))
    return result.scalar_one_or_none()


async def count_words(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(Word))
    return result.scalar_one()


async def list_words(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 50,
) -> list[Word]:
    result = await session.execute(select(Word).order_by(Word.word).offset(offset).limit(limit))
    return list(result.scalars().all())


async def upsert_word(
    session: AsyncSession,
    word: str,
    phonemes: str | None = None,
    etymology_root: str | None = None,
    definition: str | None = None,
    origin_language: str | None = None,
    language_family: str | None = None,
    historical_context: str | None = None,
    semantic_drift_history: list | None = None,
) -> Word:
    """Insert or update a word row, returning the persisted record.

    Non-None values overwrite the existing column; None values leave it unchanged
    (COALESCE semantics — safe for partial updates).
    """
    payload = {
        "phonemes": phonemes,
        "etymology_root": etymology_root,
        "definition": definition,
        "origin_language": origin_language,
        "language_family": language_family,
        "historical_context": historical_context,
        "semantic_drift_history": semantic_drift_history,
    }
    non_null = {k: v for k, v in payload.items() if v is not None}

    if non_null:
        stmt = (
            pg_insert(Word)
            .values(word=word, **payload)
            .on_conflict_do_update(index_elements=["word"], set_=non_null)
            .returning(Word)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.scalar_one()

    # All payload values are None — insert if not exists, then return the row.
    insert_stmt = (
        pg_insert(Word)
        .values(word=word, **payload)
        .on_conflict_do_nothing()
    )
    await session.execute(insert_stmt)
    await session.commit()
    result = await session.execute(select(Word).where(Word.word == word))
    return result.scalar_one()


async def search_words(
    session: AsyncSession,
    prefix: str,
    limit: int = 20,
) -> list[Word]:
    result = await session.execute(
        select(Word)
        .where(Word.word.ilike(f"{prefix}%"))
        .order_by(Word.word)
        .limit(limit)
    )
    return list(result.scalars().all())
