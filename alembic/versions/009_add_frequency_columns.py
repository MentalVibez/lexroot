"""Add wordfreq columns to words table.

Zipf score (1–7 log scale) provides empirical corpus frequency data to
complement the structural vitality proxy. wordfreq is already registered as
a Tier 4 source in sources_catalog.py. Populated by:
    python -m ingestor.frequency_pg_importer

Revision ID: 009
Revises: 008
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("words", sa.Column("wordfreq_zipf", sa.Float, nullable=True))
    op.add_column("words", sa.Column("wordfreq_rank", sa.Integer, nullable=True))
    op.add_column("words", sa.Column("wordfreq_source_slug", sa.String(120), nullable=True))
    op.create_index("ix_words_wordfreq_zipf", "words", ["wordfreq_zipf"])


def downgrade() -> None:
    op.drop_index("ix_words_wordfreq_zipf", table_name="words")
    op.drop_column("words", "wordfreq_zipf")
    op.drop_column("words", "wordfreq_rank")
    op.drop_column("words", "wordfreq_source_slug")
