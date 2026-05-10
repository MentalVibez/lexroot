"""Add definition source metadata

Revision ID: 004
Revises: 003
Create Date: 2026-05-09

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("words", sa.Column("definition_source_slug", sa.String(120), nullable=True))
    op.add_column("words", sa.Column("definition_source_name", sa.Text(), nullable=True))
    op.add_column("words", sa.Column("definition_license", sa.String(80), nullable=True))


def downgrade() -> None:
    op.drop_column("words", "definition_license")
    op.drop_column("words", "definition_source_name")
    op.drop_column("words", "definition_source_slug")
