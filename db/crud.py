from __future__ import annotations

from difflib import SequenceMatcher
import os
from sqlalchemy import and_, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Attestation, DatasetSnapshot, Morpheme, Sense, Word, WordRelation


async def get_word(session: AsyncSession, word: str) -> Word | None:
    folded = word.casefold()
    result = await session.execute(
        select(Word)
        .where(func.lower(Word.word) == folded)
        .order_by((Word.word == word).desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_words(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(Word))
    return result.scalar_one()


async def list_words(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 50,
) -> list[Word]:
    result = await session.execute(select(Word).order_by(Word.word).offset(offset).limit(limit))
    return list(result.scalars().all())


async def upsert_word(
    session: AsyncSession,
    word: str,
    entry_type: str = "word",
    phonemes: str | None = None,
    etymology_root: str | None = None,
    definition: str | None = None,
    definition_source_slug: str | None = None,
    definition_source_name: str | None = None,
    definition_license: str | None = None,
    origin_language: str | None = None,
    language_family: str | None = None,
    historical_context: str | None = None,
    literal_meaning: str | None = None,
    figurative_meaning: str | None = None,
    example_usage: str | None = None,
    semantic_drift_history: list | None = None,
    reconstruction_level: str | None = None,
) -> Word:
    """Insert or update a word row, returning the persisted record.

    Non-None values overwrite the existing column; None values leave it unchanged
    (COALESCE semantics — safe for partial updates).
    """
    payload = {
        "entry_type": entry_type,
        "phonemes": phonemes,
        "etymology_root": etymology_root,
        "definition": definition,
        "definition_source_slug": definition_source_slug,
        "definition_source_name": definition_source_name,
        "definition_license": definition_license,
        "origin_language": origin_language,
        "language_family": language_family,
        "historical_context": historical_context,
        "literal_meaning": literal_meaning,
        "figurative_meaning": figurative_meaning,
        "example_usage": example_usage,
        "semantic_drift_history": semantic_drift_history,
        "reconstruction_level": reconstruction_level,
    }
    non_null = {k: v for k, v in payload.items() if v is not None}

    if non_null:
        stmt = (
            pg_insert(Word)
            .values(word=word, **payload)
            .on_conflict_do_update(index_elements=["word"], set_=non_null)
            .returning(Word)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.scalar_one()

    # All payload values are None — insert if not exists, then return the row.
    insert_stmt = (
        pg_insert(Word)
        .values(word=word, **payload)
        .on_conflict_do_nothing()
    )
    await session.execute(insert_stmt)
    await session.commit()
    result = await session.execute(select(Word).where(Word.word == word))
    return result.scalar_one()


async def search_words(
    session: AsyncSession,
    prefix: str,
    limit: int = 20,
) -> list[Word]:
    folded = prefix.casefold()
    word_priority = (
        (Word.entry_type == "word"),
        (Word.entry_type == "idiom"),
        (Word.entry_type == "medical_term"),
    )
    enrichment_priority = (
        Word.semantic_drift_history.is_not(None),
        Word.origin_language.is_not(None),
        Word.definition_source_slug.is_not(None),
    )
    result = await session.execute(
        select(Word)
        .where(Word.word.ilike(f"{prefix}%"))
        .order_by(
            (func.lower(Word.word) == folded).desc(),
            *[expr.desc() for expr in word_priority],
            *[expr.desc() for expr in enrichment_priority],
            Word.wordfreq_zipf.desc().nullslast(),
            func.length(Word.word),
            Word.word,
        )
        .limit(limit)
    )
    return list(result.scalars().all())


async def suggest_words(
    session: AsyncSession,
    query: str,
    limit: int = 5,
) -> list[Word]:
    """Return likely spelling suggestions from existing lexicon rows."""
    folded = query.strip().casefold()
    if len(folded) < 4:
        return []

    result = await session.execute(
        select(Word)
        .where(func.length(Word.word).between(max(1, len(folded) - 2), len(folded) + 2))
        .order_by(Word.wordfreq_rank.is_(None), Word.wordfreq_rank, Word.word)
        .limit(1000)
    )
    candidates = list(result.scalars().all())
    scored: list[tuple[float, int, str, Word]] = []
    for row in candidates:
        candidate = row.word.casefold()
        if candidate == folded:
            continue
        score = SequenceMatcher(None, folded, candidate).ratio()
        if score >= 0.72:
            rank = row.wordfreq_rank if row.wordfreq_rank is not None else 999_999_999
            scored.append((score, rank, row.word, row))

    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [row for _, _, _, row in scored[:limit]]


async def upsert_sense(
    session: AsyncSession,
    sense_id: str,
    word: str,
    definition: str,
    entry_type: str = "word",
    part_of_speech: str | None = None,
    meaning_type: str = "attested",
    register: str | None = None,
    domain: str | None = None,
    era_name: str | None = None,
    first_attested_year: int | None = None,
    last_attested_year: int | None = None,
    first_attested_source: str | None = None,
    source_slug: str | None = None,
    confidence: str = "medium",
    confidence_reason: str | None = None,
    evidence_grade: str | None = None,
    citation: str | None = None,
    page: str | None = None,
    entry_headword: str | None = None,
    source_url: str | None = None,
    access_date: str | None = None,
    review_status: str | None = None,
    semantic_change_type: str | None = None,
    origin_status: str | None = None,
    usage_region: str | None = None,
    usage_register: str | None = None,
    notes: str | None = None,
    reconstruction_level: str | None = None,
    learner_level: str | None = None,
) -> Sense:
    payload = {
        "word": word,
        "entry_type": entry_type,
        "part_of_speech": part_of_speech,
        "definition": definition,
        "meaning_type": meaning_type,
        "register": register,
        "domain": domain,
        "era_name": era_name,
        "first_attested_year": first_attested_year,
        "last_attested_year": last_attested_year,
        "first_attested_source": first_attested_source,
        "source_slug": source_slug,
        "confidence": confidence,
        "confidence_reason": confidence_reason,
        "evidence_grade": evidence_grade,
        "citation": citation,
        "page": page,
        "entry_headword": entry_headword,
        "source_url": source_url,
        "access_date": access_date,
        "review_status": review_status,
        "semantic_change_type": semantic_change_type,
        "origin_status": origin_status,
        "usage_region": usage_region,
        "usage_register": usage_register,
        "notes": notes,
        "reconstruction_level": reconstruction_level,
        "learner_level": learner_level,
    }
    existing = await get_sense(session, sense_id)
    if existing is None:
        existing = Sense(sense_id=sense_id, **payload)
        session.add(existing)
    else:
        for key, value in payload.items():
            setattr(existing, key, value)
    await session.commit()
    await session.refresh(existing)
    return existing


async def list_senses(session: AsyncSession, word: str) -> list[Sense]:
    result = await session.execute(
        select(Sense)
        .where(Sense.word == word)
        .order_by(Sense.first_attested_year, Sense.sense_id)
    )
    return list(result.scalars().all())


async def get_senses_by_era(
    session: AsyncSession, word: str, era_name: str
) -> list[Sense]:
    result = await session.execute(
        select(Sense)
        .where(Sense.word == word, Sense.era_name == era_name)
        .order_by(Sense.evidence_grade, Sense.confidence)
    )
    return list(result.scalars().all())


async def bulk_get_senses_by_era(
    session: AsyncSession, words: list[str], era_name: str
) -> dict[str, list[Sense]]:
    """Fetch era senses for multiple words in one query."""
    from sqlalchemy import and_
    result = await session.execute(
        select(Sense).where(
            and_(Sense.word.in_(words), Sense.era_name == era_name)
        )
    )
    rows = result.scalars().all()
    out: dict[str, list[Sense]] = {w: [] for w in words}
    for row in rows:
        out[row.word].append(row)
    return out


async def bulk_get_senses_all_eras(
    session: AsyncSession, words: list[str]
) -> dict[str, list[Sense]]:
    """Fetch senses across every era for multiple words in one query.

    Like :func:`bulk_get_senses_by_era` but without the era filter — used by the
    era-check "scan all eras" path so a passage surfaces meaning shifts no matter
    which era the reader guesses.
    """
    result = await session.execute(
        select(Sense).where(Sense.word.in_(words))
    )
    rows = result.scalars().all()
    out: dict[str, list[Sense]] = {w: [] for w in words}
    for row in rows:
        out[row.word].append(row)
    return out


async def bulk_get_words(
    session: AsyncSession, words: list[str]
) -> dict[str, Word]:
    """Fetch Word rows for multiple words in one query."""
    result = await session.execute(select(Word).where(Word.word.in_(words)))
    return {row.word: row for row in result.scalars().all()}


async def get_sense(session: AsyncSession, sense_id: str) -> Sense | None:
    result = await session.execute(select(Sense).where(Sense.sense_id == sense_id))
    return result.scalar_one_or_none()


async def add_attestation(
    session: AsyncSession,
    sense_id: str,
    word: str,
    quote: str | None = None,
    quote_year: int | None = None,
    quote_author: str | None = None,
    quote_work: str | None = None,
    source_slug: str | None = None,
    attestation_type: str = "historical_dictionary",
    citation: str | None = None,
    evidence_grade: str | None = None,
    confidence_reason: str | None = None,
    page: str | None = None,
    entry_headword: str | None = None,
    source_url: str | None = None,
    access_date: str | None = None,
    review_status: str | None = None,
    notes: str | None = None,
) -> Attestation:
    row = Attestation(
        sense_id=sense_id,
        word=word,
        quote=quote,
        quote_year=quote_year,
        quote_author=quote_author,
        quote_work=quote_work,
        source_slug=source_slug,
        attestation_type=attestation_type,
        citation=citation,
        evidence_grade=evidence_grade,
        confidence_reason=confidence_reason,
        page=page,
        entry_headword=entry_headword,
        source_url=source_url,
        access_date=access_date,
        review_status=review_status,
        notes=notes,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def list_attestations(session: AsyncSession, sense_id: str) -> list[Attestation]:
    result = await session.execute(
        select(Attestation)
        .where(Attestation.sense_id == sense_id)
        .order_by(Attestation.quote_year, Attestation.id)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Dataset snapshots
# ---------------------------------------------------------------------------

async def create_snapshot(
    session: AsyncSession,
    tag: str,
    description: str | None = None,
) -> DatasetSnapshot:
    """Package current words/senses/attestations into a citable JSONB snapshot."""
    words = await session.execute(select(Word))
    senses = await session.execute(select(Sense))
    attestations = await session.execute(select(Attestation))

    word_rows = [
        {c.key: getattr(r, c.key) for c in Word.__table__.columns}
        for r in words.scalars().all()
    ]
    sense_rows = [
        {c.key: getattr(r, c.key) for c in Sense.__table__.columns}
        for r in senses.scalars().all()
    ]
    att_rows = [
        {c.key: getattr(r, c.key) for c in Attestation.__table__.columns}
        for r in attestations.scalars().all()
    ]

    # Serialize datetime objects to ISO strings for JSONB compatibility
    def _serialize(rows: list[dict]) -> list[dict]:
        out = []
        for row in rows:
            out.append({
                k: v.isoformat() if hasattr(v, "isoformat") else v
                for k, v in row.items()
            })
        return out

    snapshot = DatasetSnapshot(
        tag=tag,
        description=description,
        word_count=len(word_rows),
        sense_count=len(sense_rows),
        attestation_count=len(att_rows),
        schema_version=os.getenv("ALEMBIC_VERSION", "008"),
        snapshot_data={
            "words": _serialize(word_rows),
            "senses": _serialize(sense_rows),
            "attestations": _serialize(att_rows),
        },
    )
    session.add(snapshot)
    await session.commit()
    await session.refresh(snapshot)
    return snapshot


async def list_snapshots(session: AsyncSession) -> list[DatasetSnapshot]:
    """Return all snapshot headers — no snapshot_data (too large for lists)."""
    result = await session.execute(
        select(
            DatasetSnapshot.id,
            DatasetSnapshot.tag,
            DatasetSnapshot.description,
            DatasetSnapshot.created_at,
            DatasetSnapshot.word_count,
            DatasetSnapshot.sense_count,
            DatasetSnapshot.attestation_count,
            DatasetSnapshot.schema_version,
        ).order_by(DatasetSnapshot.created_at.desc())
    )
    # Return as lightweight objects using the full model but without data
    full = await session.execute(
        select(DatasetSnapshot).order_by(DatasetSnapshot.created_at.desc())
    )
    return list(full.scalars().all())


async def get_snapshot(session: AsyncSession, tag: str) -> DatasetSnapshot | None:
    result = await session.execute(
        select(DatasetSnapshot).where(DatasetSnapshot.tag == tag)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Semantic field queries
# ---------------------------------------------------------------------------

async def list_senses_by_field(
    session: AsyncSession,
    domain: str | None = None,
    semantic_change_type: str | None = None,
    era_name: str | None = None,
    limit: int = 50,
) -> list[Sense]:
    filters = []
    if domain:
        filters.append(Sense.domain == domain)
    if semantic_change_type:
        filters.append(Sense.semantic_change_type == semantic_change_type)
    if era_name:
        filters.append(Sense.era_name == era_name)
    stmt = select(Sense)
    if filters:
        stmt = stmt.where(and_(*filters))
    stmt = stmt.order_by(Sense.evidence_grade, Sense.first_attested_year).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_senses_by_review_status(
    session: AsyncSession,
    review_status: str,
    word: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Sense]:
    filters = [Sense.review_status == review_status]
    if word:
        filters.append(Sense.word == word)
    result = await session.execute(
        select(Sense)
        .where(and_(*filters))
        .order_by(Sense.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_sense_review_status(
    session: AsyncSession,
    sense_id: str,
    review_status: str,
    reviewer_notes: str | None = None,
) -> Sense | None:
    sense = await get_sense(session, sense_id)
    if sense is None:
        return None
    sense.review_status = review_status
    if reviewer_notes is not None:
        sense.reviewer_notes = reviewer_notes
    await session.commit()
    await session.refresh(sense)
    return sense


# ---------------------------------------------------------------------------
# Frequency queries
# ---------------------------------------------------------------------------

async def list_words_with_frequency(
    session: AsyncSession,
    min_zipf: float = 0.0,
    limit: int = 50,
) -> list[Word]:
    result = await session.execute(
        select(Word)
        .where(Word.wordfreq_zipf >= min_zipf)
        .order_by(Word.wordfreq_zipf.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Word relations
# ---------------------------------------------------------------------------

async def add_word_relation(
    session: AsyncSession,
    from_word: str,
    to_word: str,
    relation_type: str,
    era_name: str | None = None,
    source_slug: str | None = None,
    confidence: str = "medium",
    notes: str | None = None,
) -> WordRelation:
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    stmt = (
        pg_insert(WordRelation)
        .values(
            from_word=from_word,
            to_word=to_word,
            relation_type=relation_type,
            era_name=era_name,
            source_slug=source_slug,
            confidence=confidence,
            notes=notes,
        )
        .on_conflict_do_update(
            constraint="uq_word_relations",
            set_={"confidence": confidence, "notes": notes, "source_slug": source_slug},
        )
        .returning(WordRelation)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one()


async def get_word_relations(
    session: AsyncSession,
    word: str,
    relation_type: str | None = None,
) -> list[WordRelation]:
    filters = [WordRelation.from_word == word]
    if relation_type:
        filters.append(WordRelation.relation_type == relation_type)
    result = await session.execute(
        select(WordRelation).where(and_(*filters)).order_by(WordRelation.relation_type)
    )
    return list(result.scalars().all())


async def get_word_family(
    session: AsyncSession,
    root_word: str,
    depth: int = 3,
    limit: int = 50,
) -> list[str]:
    """BFS traversal of derived_from / root_of edges, returning related word strings."""
    visited: set[str] = {root_word}
    frontier = [root_word]
    for _ in range(depth):
        if not frontier or len(visited) >= limit:
            break
        result = await session.execute(
            select(WordRelation.to_word).where(
                and_(
                    WordRelation.from_word.in_(frontier),
                    WordRelation.relation_type.in_(("derived_from", "root_of")),
                )
            )
        )
        next_words = [w for w in result.scalars().all() if w not in visited]
        visited.update(next_words)
        frontier = next_words
    return sorted(visited - {root_word})[:limit]


# ---------------------------------------------------------------------------
# Morphemes
# ---------------------------------------------------------------------------

async def upsert_morpheme(
    session: AsyncSession,
    word: str,
    morpheme: str,
    role: str,
    origin_language: str | None = None,
    gloss: str | None = None,
    position: int | None = None,
    source_slug: str | None = None,
) -> Morpheme:
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    stmt = (
        pg_insert(Morpheme)
        .values(
            word=word,
            morpheme=morpheme,
            role=role,
            origin_language=origin_language,
            gloss=gloss,
            position=position,
            source_slug=source_slug,
        )
        .on_conflict_do_update(
            constraint="uq_morphemes",
            set_={"origin_language": origin_language, "gloss": gloss, "source_slug": source_slug},
        )
        .returning(Morpheme)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one()


async def get_morphemes(session: AsyncSession, word: str) -> list[Morpheme]:
    result = await session.execute(
        select(Morpheme)
        .where(Morpheme.word == word)
        .order_by(Morpheme.position, Morpheme.role)
    )
    return list(result.scalars().all())


async def find_words_by_morpheme(
    session: AsyncSession,
    morpheme: str,
    role: str | None = None,
    limit: int = 50,
) -> list[str]:
    filters = [Morpheme.morpheme == morpheme]
    if role:
        filters.append(Morpheme.role == role)
    result = await session.execute(
        select(Morpheme.word).where(and_(*filters)).order_by(Morpheme.word).limit(limit)
    )
    return list(result.scalars().all())
