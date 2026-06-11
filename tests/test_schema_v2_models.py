from __future__ import annotations

from db.database import Base


def test_v2_schema_tables_registered():
    tables = Base.metadata.tables

    assert "language_stages" in tables
    assert "lexemes" in tables
    assert "forms" in tables
    assert "etymology_claims" in tables
    assert "etymology_steps" in tables
    assert "evidence_items" in tables
    assert "sense_change_tags" in tables


def test_lexeme_and_claim_constraints_registered():
    lexemes = Base.metadata.tables["lexemes"]
    etymology_steps = Base.metadata.tables["etymology_steps"]
    sense_change_tags = Base.metadata.tables["sense_change_tags"]

    assert "canonical_word_id" in lexemes.c
    assert "uq_etymology_steps_claim_order" in {c.name for c in etymology_steps.constraints if c.name}
    assert "uq_sense_change_tags" in {c.name for c in sense_change_tags.constraints if c.name}
