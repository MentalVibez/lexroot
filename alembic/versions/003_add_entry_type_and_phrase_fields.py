"""Add entry type and phrase fields to words

Revision ID: 003
Revises: 002
Create Date: 2026-05-09

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "words",
        sa.Column("entry_type", sa.String(40), server_default="word", nullable=False),
    )
    op.add_column("words", sa.Column("literal_meaning", sa.Text(), nullable=True))
    op.add_column("words", sa.Column("figurative_meaning", sa.Text(), nullable=True))
    op.add_column("words", sa.Column("example_usage", sa.Text(), nullable=True))
    op.create_index(op.f("ix_words_entry_type"), "words", ["entry_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_words_entry_type"), table_name="words")
    op.drop_column("words", "example_usage")
    op.drop_column("words", "figurative_meaning")
    op.drop_column("words", "literal_meaning")
    op.drop_column("words", "entry_type")
