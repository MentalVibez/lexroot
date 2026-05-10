"""Add word_relations table for semantic and etymological relationships

Revision ID: 012
Revises: 011
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "word_relations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("from_word", sa.String(255), nullable=False),
        sa.Column("to_word", sa.String(255), nullable=False),
        sa.Column("relation_type", sa.String(60), nullable=False),
        sa.Column("era_name", sa.String(120), nullable=True),
        sa.Column("source_slug", sa.String(120), nullable=True),
        sa.Column("confidence", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("from_word", "to_word", "relation_type", name="uq_word_relations"),
    )
    op.create_index("ix_word_relations_from", "word_relations", ["from_word"])
    op.create_index("ix_word_relations_type", "word_relations", ["relation_type"])


def downgrade() -> None:
    op.drop_index("ix_word_relations_type", table_name="word_relations")
    op.drop_index("ix_word_relations_from", table_name="word_relations")
    op.drop_table("word_relations")
