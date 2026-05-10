"""Add pgvector embedding column to senses table.

Adds a `embedding` vector(1536) column to `senses` for storing dense
semantic embeddings per sense definition. Used to compute cosine similarity
between consecutive-era senses — the real drift velocity score (D) that
will replace the current structural proxy in living_lexicon/vitality.py.

Requires the pgvector Postgres extension. If it's not available the
migration will fail cleanly — install via:
    CREATE EXTENSION IF NOT EXISTS vector;
or set SKIP_VECTOR_MIGRATION=1 in the environment to skip this upgrade.

Revision ID: 007
Revises: 006
"""
from __future__ import annotations

import os
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if os.getenv("SKIP_VECTOR_MIGRATION", "").lower() in ("1", "true", "yes"):
        return

    # Enable pgvector extension (no-op if already enabled)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Add embedding column — nullable so existing rows are unaffected
    op.add_column(
        "senses",
        sa.Column(
            "embedding",
            sa.Text(),  # stored as text until sqlalchemy-pgvector is installed;
                        # cast to vector(1536) in queries: embedding::vector
            nullable=True,
            comment="1536-dim dense embedding of the sense definition. "
                    "Populated by ingestor/embed_senses.py. "
                    "Cast to vector(1536) for cosine similarity queries.",
        ),
    )

    # Partial index — only index rows where embedding is present
    op.create_index(
        "ix_senses_embedding_not_null",
        "senses",
        ["sense_id"],
        postgresql_where=sa.text("embedding IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_senses_embedding_not_null", table_name="senses")
    op.drop_column("senses", "embedding")
