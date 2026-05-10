"""Add evidence quality fields

Revision ID: 006
Revises: 005
Create Date: 2026-05-09

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("senses", sa.Column("first_attested_source", sa.Text(), nullable=True))
    op.add_column("senses", sa.Column("confidence_reason", sa.Text(), nullable=True))
    op.add_column("senses", sa.Column("evidence_grade", sa.String(1), nullable=True))
    op.add_column("senses", sa.Column("citation", sa.Text(), nullable=True))
    op.add_column("senses", sa.Column("page", sa.String(80), nullable=True))
    op.add_column("senses", sa.Column("entry_headword", sa.String(255), nullable=True))
    op.add_column("senses", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column("senses", sa.Column("access_date", sa.String(40), nullable=True))
    op.add_column("senses", sa.Column("review_status", sa.String(40), nullable=True))
    op.add_column("senses", sa.Column("semantic_change_type", sa.String(80), nullable=True))
    op.add_column("senses", sa.Column("origin_status", sa.String(80), nullable=True))
    op.add_column("senses", sa.Column("usage_region", sa.String(120), nullable=True))
    op.add_column("senses", sa.Column("usage_register", sa.String(80), nullable=True))
    op.create_index(op.f("ix_senses_evidence_grade"), "senses", ["evidence_grade"], unique=False)
    op.create_index(op.f("ix_senses_review_status"), "senses", ["review_status"], unique=False)
    op.create_index(op.f("ix_senses_semantic_change_type"), "senses", ["semantic_change_type"], unique=False)

    op.add_column("attestations", sa.Column("evidence_grade", sa.String(1), nullable=True))
    op.add_column("attestations", sa.Column("confidence_reason", sa.Text(), nullable=True))
    op.add_column("attestations", sa.Column("page", sa.String(80), nullable=True))
    op.add_column("attestations", sa.Column("entry_headword", sa.String(255), nullable=True))
    op.add_column("attestations", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column("attestations", sa.Column("access_date", sa.String(40), nullable=True))
    op.add_column("attestations", sa.Column("review_status", sa.String(40), nullable=True))
    op.create_index(op.f("ix_attestations_evidence_grade"), "attestations", ["evidence_grade"], unique=False)
    op.create_index(op.f("ix_attestations_review_status"), "attestations", ["review_status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_attestations_review_status"), table_name="attestations")
    op.drop_index(op.f("ix_attestations_evidence_grade"), table_name="attestations")
    op.drop_column("attestations", "review_status")
    op.drop_column("attestations", "access_date")
    op.drop_column("attestations", "source_url")
    op.drop_column("attestations", "entry_headword")
    op.drop_column("attestations", "page")
    op.drop_column("attestations", "confidence_reason")
    op.drop_column("attestations", "evidence_grade")

    op.drop_index(op.f("ix_senses_semantic_change_type"), table_name="senses")
    op.drop_index(op.f("ix_senses_review_status"), table_name="senses")
    op.drop_index(op.f("ix_senses_evidence_grade"), table_name="senses")
    op.drop_column("senses", "usage_register")
    op.drop_column("senses", "usage_region")
    op.drop_column("senses", "origin_status")
    op.drop_column("senses", "semantic_change_type")
    op.drop_column("senses", "review_status")
    op.drop_column("senses", "access_date")
    op.drop_column("senses", "source_url")
    op.drop_column("senses", "entry_headword")
    op.drop_column("senses", "page")
    op.drop_column("senses", "citation")
    op.drop_column("senses", "evidence_grade")
    op.drop_column("senses", "confidence_reason")
    op.drop_column("senses", "first_attested_source")
