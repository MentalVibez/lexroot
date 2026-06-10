import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db import crud
from db.database import Base
from db.models import Word


@pytest.mark.asyncio
async def test_search_words_prioritizes_exact_and_enriched_word_entries():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        session.add_all([
            Word(word="monumbo", entry_type="word", definition="A Papuan language."),
            Word(
                word="monument",
                entry_type="word",
                definition="A memorial object.",
                origin_language="Latin",
            ),
            Word(word="monumental", entry_type="word", definition="Very large."),
            Word(word="monument to memory", entry_type="idiom", definition="A phrase."),
        ])
        await session.commit()

        rows = await crud.search_words(session, "monu", limit=4)

    await engine.dispose()
    assert [row.word for row in rows][:3] == ["monument", "monumbo", "monumental"]
