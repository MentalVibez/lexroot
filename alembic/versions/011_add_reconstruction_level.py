"""Add reconstruction_level to words and senses

Revision ID: 011
Revises: 010
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "words",
        sa.Column("reconstruction_level", sa.String(20), nullable=True, server_default="attested"),
    )
    op.add_column(
        "senses",
        sa.Column("reconstruction_level", sa.String(20), nullable=True, server_default="attested"),
    )
    op.add_column(
        "senses",
        sa.Column("learner_level", sa.String(20), nullable=True, server_default="intermediate"),
    )


def downgrade() -> None:
    op.drop_column("senses", "learner_level")
    op.drop_column("senses", "reconstruction_level")
    op.drop_column("words", "reconstruction_level")
