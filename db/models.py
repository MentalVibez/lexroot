from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text, VARCHAR, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from db.database import Base


class _PortableJSONB(TypeDecorator):
    """Uses JSONB on PostgreSQL; falls back to JSON on other databases (e.g. SQLite in tests)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class Word(Base):
    """Flat relational index for the word corpus.

    semantic_drift_history stores a JSON array of era records aligned with
    living_lexicon.models.EraRecord — each entry has keys:
      era_name, start_year, end_year, meaning, usage_example, source_slug
    """

    __tablename__ = "words"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phonemes: Mapped[str | None] = mapped_column(Text, nullable=True)
    etymology_root: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin_language: Mapped[str | None] = mapped_column(VARCHAR(100), nullable=True)
    language_family: Mapped[str | None] = mapped_column(VARCHAR(100), nullable=True)
    historical_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    semantic_drift_history: Mapped[list | None] = mapped_column(_PortableJSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Word id={self.id} word={self.word!r}>"
