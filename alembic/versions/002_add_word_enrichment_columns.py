"""Add definition, origin_language, language_family, historical_context to words

Revision ID: 002
Revises: 001
Create Date: 2026-05-08

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("words", sa.Column("definition", sa.Text(), nullable=True))
    op.add_column("words", sa.Column("origin_language", sa.String(100), nullable=True))
    op.add_column("words", sa.Column("language_family", sa.String(100), nullable=True))
    op.add_column("words", sa.Column("historical_context", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("words", "historical_context")
    op.drop_column("words", "language_family")
    op.drop_column("words", "origin_language")
    op.drop_column("words", "definition")
