"""Add dataset_snapshots table for reproducible research citations.

Researchers can create a named snapshot of the full sense+attestation corpus
before submitting a paper. The tag is citable; the export endpoint streams the
exact data used for any quantitative analysis.

Revision ID: 008
Revises: 007
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dataset_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tag", sa.String(120), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("word_count", sa.Integer, nullable=True),
        sa.Column("sense_count", sa.Integer, nullable=True),
        sa.Column("attestation_count", sa.Integer, nullable=True),
        sa.Column("schema_version", sa.String(20), nullable=True),
        sa.Column("snapshot_data", JSONB, nullable=False),
    )
    op.create_index("ix_dataset_snapshots_tag", "dataset_snapshots", ["tag"])


def downgrade() -> None:
    op.drop_index("ix_dataset_snapshots_tag", table_name="dataset_snapshots")
    op.drop_table("dataset_snapshots")
