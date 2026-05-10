"""Add senses and attestations

Revision ID: 005
Revises: 004
Create Date: 2026-05-09

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "senses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sense_id", sa.String(255), nullable=False),
        sa.Column("word", sa.String(255), nullable=False),
        sa.Column("entry_type", sa.String(40), nullable=False),
        sa.Column("part_of_speech", sa.String(80), nullable=True),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("meaning_type", sa.String(80), nullable=False),
        sa.Column("register", sa.String(80), nullable=True),
        sa.Column("domain", sa.String(120), nullable=True),
        sa.Column("era_name", sa.String(120), nullable=True),
        sa.Column("first_attested_year", sa.Integer(), nullable=True),
        sa.Column("last_attested_year", sa.Integer(), nullable=True),
        sa.Column("source_slug", sa.String(120), nullable=True),
        sa.Column("confidence", sa.String(40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sense_id", name="uq_senses_sense_id"),
    )
    op.create_index(op.f("ix_senses_sense_id"), "senses", ["sense_id"], unique=False)
    op.create_index(op.f("ix_senses_word"), "senses", ["word"], unique=False)
    op.create_index(op.f("ix_senses_entry_type"), "senses", ["entry_type"], unique=False)
    op.create_index(op.f("ix_senses_era_name"), "senses", ["era_name"], unique=False)

    op.create_table(
        "attestations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sense_id", sa.String(255), nullable=False),
        sa.Column("word", sa.String(255), nullable=False),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("quote_year", sa.Integer(), nullable=True),
        sa.Column("quote_author", sa.String(255), nullable=True),
        sa.Column("quote_work", sa.String(255), nullable=True),
        sa.Column("source_slug", sa.String(120), nullable=True),
        sa.Column("attestation_type", sa.String(80), nullable=False),
        sa.Column("citation", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_attestations_sense_id"), "attestations", ["sense_id"], unique=False)
    op.create_index(op.f("ix_attestations_word"), "attestations", ["word"], unique=False)
    op.create_index(op.f("ix_attestations_quote_year"), "attestations", ["quote_year"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_attestations_quote_year"), table_name="attestations")
    op.drop_index(op.f("ix_attestations_word"), table_name="attestations")
    op.drop_index(op.f("ix_attestations_sense_id"), table_name="attestations")
    op.drop_table("attestations")
    op.drop_index(op.f("ix_senses_era_name"), table_name="senses")
    op.drop_index(op.f("ix_senses_entry_type"), table_name="senses")
    op.drop_index(op.f("ix_senses_word"), table_name="senses")
    op.drop_index(op.f("ix_senses_sense_id"), table_name="senses")
    op.drop_table("senses")
