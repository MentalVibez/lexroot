"""Add lexeme backbone tables for v2 historical-linguistics schema

Revision ID: 014
Revises: 013
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "language_stages",
        sa.Column("slug", sa.String(120), primary_key=True),
        sa.Column("display_name", sa.String(255), nullable=False, unique=True),
        sa.Column("parent_slug", sa.String(120), sa.ForeignKey("language_stages.slug"), nullable=True),
        sa.Column("family", sa.String(120), nullable=True),
        sa.Column("period_start_year", sa.Integer, nullable=True),
        sa.Column("period_end_year", sa.Integer, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
    )
    op.create_index("ix_language_stages_parent_slug", "language_stages", ["parent_slug"])
    op.create_index("ix_language_stages_family", "language_stages", ["family"])

    op.create_table(
        "lexemes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("lemma", sa.String(255), nullable=False),
        sa.Column("language_stage_slug", sa.String(120), sa.ForeignKey("language_stages.slug"), nullable=True),
        sa.Column("entry_type", sa.String(40), nullable=False, server_default="word"),
        sa.Column("part_of_speech", sa.String(80), nullable=True),
        sa.Column("canonical_word_id", sa.Integer, sa.ForeignKey("words.id"), nullable=True, unique=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_lexemes_lemma", "lexemes", ["lemma"])
    op.create_index("ix_lexemes_language_stage_slug", "lexemes", ["language_stage_slug"])
    op.create_index("ix_lexemes_entry_type", "lexemes", ["entry_type"])
    op.create_index("ix_lexemes_part_of_speech", "lexemes", ["part_of_speech"])

    op.create_table(
        "forms",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("lexeme_id", sa.Integer, sa.ForeignKey("lexemes.id"), nullable=False),
        sa.Column("form", sa.String(255), nullable=False),
        sa.Column("normalized_form", sa.String(255), nullable=True),
        sa.Column("language_stage_slug", sa.String(120), sa.ForeignKey("language_stages.slug"), nullable=True),
        sa.Column("start_year", sa.Integer, nullable=True),
        sa.Column("end_year", sa.Integer, nullable=True),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_forms_lexeme_id", "forms", ["lexeme_id"])
    op.create_index("ix_forms_form", "forms", ["form"])
    op.create_index("ix_forms_normalized_form", "forms", ["normalized_form"])
    op.create_index("ix_forms_language_stage_slug", "forms", ["language_stage_slug"])

    op.create_table(
        "etymology_claims",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("subject_type", sa.String(40), nullable=False),
        sa.Column("subject_id", sa.Integer, nullable=False),
        sa.Column("claim_type", sa.String(40), nullable=False),
        sa.Column("confidence", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("dispute_status", sa.String(40), nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("source_slug", sa.String(120), nullable=True),
        sa.Column("citation", sa.Text, nullable=True),
        sa.Column("evidence_grade", sa.String(1), nullable=True),
        sa.Column("review_status", sa.String(40), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_etymology_claims_subject_type", "etymology_claims", ["subject_type"])
    op.create_index("ix_etymology_claims_subject_id", "etymology_claims", ["subject_id"])
    op.create_index("ix_etymology_claims_claim_type", "etymology_claims", ["claim_type"])
    op.create_index("ix_etymology_claims_dispute_status", "etymology_claims", ["dispute_status"])
    op.create_index("ix_etymology_claims_source_slug", "etymology_claims", ["source_slug"])
    op.create_index("ix_etymology_claims_evidence_grade", "etymology_claims", ["evidence_grade"])
    op.create_index("ix_etymology_claims_review_status", "etymology_claims", ["review_status"])

    op.create_table(
        "etymology_steps",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("claim_id", sa.Integer, sa.ForeignKey("etymology_claims.id"), nullable=False),
        sa.Column("step_order", sa.Integer, nullable=False),
        sa.Column("from_form", sa.String(255), nullable=True),
        sa.Column("from_language_stage_slug", sa.String(120), sa.ForeignKey("language_stages.slug"), nullable=True),
        sa.Column("to_form", sa.String(255), nullable=True),
        sa.Column("to_language_stage_slug", sa.String(120), sa.ForeignKey("language_stages.slug"), nullable=True),
        sa.Column("semantic_note", sa.Text, nullable=True),
        sa.Column("phonological_note", sa.Text, nullable=True),
        sa.Column("morphological_note", sa.Text, nullable=True),
        sa.Column("is_reconstructed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("claim_id", "step_order", name="uq_etymology_steps_claim_order"),
    )
    op.create_index("ix_etymology_steps_claim_id", "etymology_steps", ["claim_id"])
    op.create_index("ix_etymology_steps_from_language_stage_slug", "etymology_steps", ["from_language_stage_slug"])
    op.create_index("ix_etymology_steps_to_language_stage_slug", "etymology_steps", ["to_language_stage_slug"])

    op.create_table(
        "evidence_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("subject_type", sa.String(40), nullable=False),
        sa.Column("subject_id", sa.Integer, nullable=False),
        sa.Column("evidence_type", sa.String(40), nullable=False),
        sa.Column("source_slug", sa.String(120), nullable=True),
        sa.Column("citation", sa.Text, nullable=True),
        sa.Column("page", sa.String(80), nullable=True),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("access_date", sa.String(40), nullable=True),
        sa.Column("evidence_grade", sa.String(1), nullable=True),
        sa.Column("confidence_reason", sa.Text, nullable=True),
        sa.Column("review_status", sa.String(40), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evidence_items_subject_type", "evidence_items", ["subject_type"])
    op.create_index("ix_evidence_items_subject_id", "evidence_items", ["subject_id"])
    op.create_index("ix_evidence_items_evidence_type", "evidence_items", ["evidence_type"])
    op.create_index("ix_evidence_items_source_slug", "evidence_items", ["source_slug"])
    op.create_index("ix_evidence_items_evidence_grade", "evidence_items", ["evidence_grade"])
    op.create_index("ix_evidence_items_review_status", "evidence_items", ["review_status"])

    op.create_table(
        "sense_change_tags",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("sense_id", sa.String(255), sa.ForeignKey("senses.sense_id"), nullable=False),
        sa.Column("change_type", sa.String(80), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_slug", sa.String(120), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.UniqueConstraint("sense_id", "change_type", name="uq_sense_change_tags"),
    )
    op.create_index("ix_sense_change_tags_sense_id", "sense_change_tags", ["sense_id"])
    op.create_index("ix_sense_change_tags_change_type", "sense_change_tags", ["change_type"])

    op.execute(
        """
        INSERT INTO lexemes (lemma, entry_type, canonical_word_id, notes)
        SELECT word, entry_type, id, 'Backfilled from legacy words table during v2 lexeme migration'
        FROM words
        """
    )


def downgrade() -> None:
    op.drop_index("ix_sense_change_tags_change_type", table_name="sense_change_tags")
    op.drop_index("ix_sense_change_tags_sense_id", table_name="sense_change_tags")
    op.drop_table("sense_change_tags")

    op.drop_index("ix_evidence_items_review_status", table_name="evidence_items")
    op.drop_index("ix_evidence_items_evidence_grade", table_name="evidence_items")
    op.drop_index("ix_evidence_items_source_slug", table_name="evidence_items")
    op.drop_index("ix_evidence_items_evidence_type", table_name="evidence_items")
    op.drop_index("ix_evidence_items_subject_id", table_name="evidence_items")
    op.drop_index("ix_evidence_items_subject_type", table_name="evidence_items")
    op.drop_table("evidence_items")

    op.drop_index("ix_etymology_steps_to_language_stage_slug", table_name="etymology_steps")
    op.drop_index("ix_etymology_steps_from_language_stage_slug", table_name="etymology_steps")
    op.drop_index("ix_etymology_steps_claim_id", table_name="etymology_steps")
    op.drop_table("etymology_steps")

    op.drop_index("ix_etymology_claims_review_status", table_name="etymology_claims")
    op.drop_index("ix_etymology_claims_evidence_grade", table_name="etymology_claims")
    op.drop_index("ix_etymology_claims_source_slug", table_name="etymology_claims")
    op.drop_index("ix_etymology_claims_dispute_status", table_name="etymology_claims")
    op.drop_index("ix_etymology_claims_claim_type", table_name="etymology_claims")
    op.drop_index("ix_etymology_claims_subject_id", table_name="etymology_claims")
    op.drop_index("ix_etymology_claims_subject_type", table_name="etymology_claims")
    op.drop_table("etymology_claims")

    op.drop_index("ix_forms_language_stage_slug", table_name="forms")
    op.drop_index("ix_forms_normalized_form", table_name="forms")
    op.drop_index("ix_forms_form", table_name="forms")
    op.drop_index("ix_forms_lexeme_id", table_name="forms")
    op.drop_table("forms")

    op.drop_index("ix_lexemes_part_of_speech", table_name="lexemes")
    op.drop_index("ix_lexemes_entry_type", table_name="lexemes")
    op.drop_index("ix_lexemes_language_stage_slug", table_name="lexemes")
    op.drop_index("ix_lexemes_lemma", table_name="lexemes")
    op.drop_table("lexemes")

    op.drop_index("ix_language_stages_family", table_name="language_stages")
    op.drop_index("ix_language_stages_parent_slug", table_name="language_stages")
    op.drop_table("language_stages")
