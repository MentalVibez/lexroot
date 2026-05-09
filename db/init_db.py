"""
One-shot table creation. Run before first use:
  python -m db.init_db
"""
import asyncio

from db.database import Base, engine
import db.models  # noqa: F401  — register models with Base


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[init_db] words table created (or already exists).")


if __name__ == "__main__":
    asyncio.run(create_tables())
