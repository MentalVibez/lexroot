from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, SmallInteger, String, Text, UniqueConstraint, VARCHAR, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from db.database import Base


class _PortableJSONB(TypeDecorator):
    """Uses JSONB on PostgreSQL; falls back to JSON on other databases (e.g. SQLite in tests)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class DatasetSnapshot(Base):
    """A versioned, citable export of the full sense+attestation corpus."""

    __tablename__ = "dataset_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tag: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sense_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attestation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schema_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    snapshot_data: Mapped[dict] = mapped_column(_PortableJSONB, nullable=False)

    def __repr__(self) -> str:
        return f"<DatasetSnapshot tag={self.tag!r} senses={self.sense_count}>"


class LanguageStage(Base):
    """Canonical language-stage reference for etymology and historical form data."""

    __tablename__ = "language_stages"

    slug: Mapped[str] = mapped_column(String(120), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    parent_slug: Mapped[str | None] = mapped_column(
        ForeignKey("language_stages.slug"), nullable=True, index=True
    )
    family: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    period_start_year: Mapped[int | None] = mapped_column(nullable=True)
    period_end_year: Mapped[int | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<LanguageStage slug={self.slug!r}>"


class Word(Base):
    """Flat relational index for the word corpus.

    semantic_drift_history stores a JSON array of era records aligned with
    living_lexicon.models.EraRecord — each entry has keys:
      era_name, start_year, end_year, meaning, usage_example, source_slug
    """

    __tablename__ = "words"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(40), default="word", nullable=False, index=True)
    phonemes: Mapped[str | None] = mapped_column(Text, nullable=True)
    etymology_root: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition_source_slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    definition_source_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition_license: Mapped[str | None] = mapped_column(String(80), nullable=True)
    origin_language: Mapped[str | None] = mapped_column(VARCHAR(100), nullable=True)
    language_family: Mapped[str | None] = mapped_column(VARCHAR(100), nullable=True)
    historical_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    literal_meaning: Mapped[str | None] = mapped_column(Text, nullable=True)
    figurative_meaning: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_usage: Mapped[str | None] = mapped_column(Text, nullable=True)
    semantic_drift_history: Mapped[list | None] = mapped_column(_PortableJSONB, nullable=True)
    wordfreq_zipf: Mapped[float | None] = mapped_column(nullable=True, index=True)
    wordfreq_rank: Mapped[int | None] = mapped_column(nullable=True)
    wordfreq_source_slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reconstruction_level: Mapped[str | None] = mapped_column(String(20), nullable=True, default="attested")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Word id={self.id} word={self.word!r}>"


class Lexeme(Base):
    """Canonical lexical entry used as the future anchor for senses and forms."""

    __tablename__ = "lexemes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lemma: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    language_stage_slug: Mapped[str | None] = mapped_column(
        ForeignKey("language_stages.slug"), nullable=True, index=True
    )
    entry_type: Mapped[str] = mapped_column(String(40), default="word", nullable=False, index=True)
    part_of_speech: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    canonical_word_id: Mapped[int | None] = mapped_column(ForeignKey("words.id"), nullable=True, unique=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Lexeme id={self.id} lemma={self.lemma!r}>"


class Form(Base):
    """Historical or normalized surface form attached to a lexeme."""

    __tablename__ = "forms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lexeme_id: Mapped[int] = mapped_column(ForeignKey("lexemes.id"), nullable=False, index=True)
    form: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    normalized_form: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    language_stage_slug: Mapped[str | None] = mapped_column(
        ForeignKey("language_stages.slug"), nullable=True, index=True
    )
    start_year: Mapped[int | None] = mapped_column(nullable=True)
    end_year: Mapped[int | None] = mapped_column(nullable=True)
    is_preferred: Mapped[bool] = mapped_column(default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Form form={self.form!r} lexeme_id={self.lexeme_id}>"


class Sense(Base):
    """A historically scoped meaning for a word or phrase."""

    __tablename__ = "senses"
    __table_args__ = (UniqueConstraint("sense_id", name="uq_senses_sense_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sense_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    word: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(40), default="word", nullable=False, index=True)
    part_of_speech: Mapped[str | None] = mapped_column(String(80), nullable=True)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    meaning_type: Mapped[str] = mapped_column(String(80), default="attested", nullable=False)
    register: Mapped[str | None] = mapped_column(String(80), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(120), nullable=True)
    era_name: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    first_attested_year: Mapped[int | None] = mapped_column(nullable=True)
    last_attested_year: Mapped[int | None] = mapped_column(nullable=True)
    first_attested_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    confidence: Mapped[str] = mapped_column(String(40), default="medium", nullable=False)
    confidence_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_grade: Mapped[str | None] = mapped_column(String(1), nullable=True, index=True)
    citation: Mapped[str | None] = mapped_column(Text, nullable=True)
    page: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entry_headword: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    review_status: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    semantic_change_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    origin_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    usage_region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    usage_register: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reconstruction_level: Mapped[str | None] = mapped_column(String(20), nullable=True, default="attested")
    learner_level: Mapped[str | None] = mapped_column(String(20), nullable=True, default="intermediate")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )


class Attestation(Base):
    """A dated quotation or evidence object supporting a sense."""

    __tablename__ = "attestations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sense_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    word: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    quote_year: Mapped[int | None] = mapped_column(nullable=True, index=True)
    quote_author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quote_work: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    attestation_type: Mapped[str] = mapped_column(String(80), default="historical_dictionary", nullable=False)
    citation: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_grade: Mapped[str | None] = mapped_column(String(1), nullable=True, index=True)
    confidence_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    page: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entry_headword: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    review_status: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )


class EtymologyClaim(Base):
    """A source-attributed origin claim for a lexical object."""

    __tablename__ = "etymology_claims"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subject_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    claim_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    confidence: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    dispute_status: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_slug: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    citation: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_grade: Mapped[str | None] = mapped_column(String(1), nullable=True, index=True)
    review_status: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    def __repr__(self) -> str:
        return f"<EtymologyClaim id={self.id} subject={self.subject_type}:{self.subject_id}>"


class EtymologyStep(Base):
    """One ordered transmission step within an etymology claim."""

    __tablename__ = "etymology_steps"
    __table_args__ = (UniqueConstraint("claim_id", "step_order", name="uq_etymology_steps_claim_order"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("etymology_claims.id"), nullable=False, index=True)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    from_form: Mapped[str | None] = mapped_column(String(255), nullable=True)
    from_language_stage_slug: Mapped[str | None] = mapped_column(
        ForeignKey("language_stages.slug"), nullable=True, index=True
    )
    to_form: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_language_stage_slug: Mapped[str | None] = mapped_column(
        ForeignKey("language_stages.slug"), nullable=True, index=True
    )
    semantic_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    phonological_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    morphological_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_reconstructed: Mapped[bool] = mapped_column(default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<EtymologyStep claim_id={self.claim_id} order={self.step_order}>"


class EvidenceItem(Base):
    """Reusable evidence object for senses, claims, forms, or morpheme analyses."""

    __tablename__ = "evidence_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subject_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    evidence_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_slug: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    citation: Mapped[str | None] = mapped_column(Text, nullable=True)
    page: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    evidence_grade: Mapped[str | None] = mapped_column(String(1), nullable=True, index=True)
    confidence_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_status: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<EvidenceItem id={self.id} subject={self.subject_type}:{self.subject_id}>"


class WordRelation(Base):
    """A directed semantic or etymological relationship between two words."""

    __tablename__ = "word_relations"
    __table_args__ = (UniqueConstraint("from_word", "to_word", "relation_type", name="uq_word_relations"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    from_word: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    to_word: Mapped[str] = mapped_column(String(255), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    era_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    confidence: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<WordRelation {self.from_word!r} -{self.relation_type}-> {self.to_word!r}>"


class Morpheme(Base):
    """A prefix, root, suffix, or infix component of a word."""

    __tablename__ = "morphemes"
    __table_args__ = (UniqueConstraint("word", "morpheme", "role", "position", name="uq_morphemes"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    morpheme: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    origin_language: Mapped[str | None] = mapped_column(String(80), nullable=True)
    gloss: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    source_slug: Mapped[str | None] = mapped_column(String(120), nullable=True)

    def __repr__(self) -> str:
        return f"<Morpheme {self.morpheme!r} ({self.role}) of {self.word!r}>"


class SenseChangeTag(Base):
    """Normalized semantic-change tags for a sense, with one optional primary tag."""

    __tablename__ = "sense_change_tags"
    __table_args__ = (UniqueConstraint("sense_id", "change_type", name="uq_sense_change_tags"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sense_id: Mapped[str] = mapped_column(ForeignKey("senses.sense_id"), nullable=False, index=True)
    change_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(default=False, nullable=False)
    source_slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<SenseChangeTag sense_id={self.sense_id!r} change_type={self.change_type!r}>"
