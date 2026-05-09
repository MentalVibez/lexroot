"""Initial schema — words table

Revision ID: 001
Revises:
Create Date: 2026-05-08

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "words",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("word", sa.String(255), nullable=False),
        sa.Column("phonemes", sa.Text(), nullable=True),
        sa.Column("etymology_root", sa.Text(), nullable=True),
        sa.Column("semantic_drift_history", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("word"),
    )
    op.create_index(op.f("ix_words_word"), "words", ["word"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_words_word"), table_name="words")
    op.drop_table("words")
