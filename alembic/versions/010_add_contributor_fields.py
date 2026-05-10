"""Add contributor tracking fields to senses and attestations.

Enables the two-tier access model: contributors propose senses via
POST /contribute/sense (no admin token required), admins review and
publish via PATCH /admin/review/sense/{sense_id}.

submitted_by is a hashed opaque identifier — never the raw token.
reviewer_notes captures rejection reasons or editorial comments.

Revision ID: 010
Revises: 009
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("senses", "attestations"):
        op.add_column(table, sa.Column("submitted_by", sa.String(255), nullable=True))
        op.add_column(table, sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("reviewer_notes", sa.Text, nullable=True))


def downgrade() -> None:
    for table in ("senses", "attestations"):
        op.drop_column(table, "submitted_by")
        op.drop_column(table, "submitted_at")
        op.drop_column(table, "reviewer_notes")
