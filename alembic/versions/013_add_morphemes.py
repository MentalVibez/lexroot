"""Add morphemes table for prefix/root/suffix decomposition

Revision ID: 013
Revises: 012
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "morphemes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("word", sa.String(255), nullable=False),
        sa.Column("morpheme", sa.String(120), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("origin_language", sa.String(80), nullable=True),
        sa.Column("gloss", sa.Text, nullable=True),
        sa.Column("position", sa.SmallInteger, nullable=True),
        sa.Column("source_slug", sa.String(120), nullable=True),
        sa.UniqueConstraint("word", "morpheme", "role", "position", name="uq_morphemes"),
    )
    op.create_index("ix_morphemes_word", "morphemes", ["word"])
    op.create_index("ix_morphemes_morpheme", "morphemes", ["morpheme"])
    op.create_index("ix_morphemes_role", "morphemes", ["role"])


def downgrade() -> None:
    op.drop_index("ix_morphemes_role", table_name="morphemes")
    op.drop_index("ix_morphemes_morpheme", table_name="morphemes")
    op.drop_index("ix_morphemes_word", table_name="morphemes")
    op.drop_table("morphemes")
