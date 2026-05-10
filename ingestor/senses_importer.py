"""
Import historically scoped senses and attestations into PostgreSQL.

CSV files:
  Words/sources/senses.csv
  Words/sources/attestations.csv

Usage:
  python3 -m ingestor.senses_importer --dry-run
  python3 -m ingestor.senses_importer
"""
from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any


from ingestor.utils import clean_str as _clean, safe_int as _safe_int

WORDS_DIR = Path(__file__).parent.parent / "Words"
DEFAULT_SENSES = WORDS_DIR / "sources" / "senses.csv"
DEFAULT_ATTESTATIONS = WORDS_DIR / "sources" / "attestations.csv"
SYNC_URL: str = os.getenv(
    "POSTGRES_SYNC_URL",
    "postgresql://lexicon:lexicon_secret@localhost:5432/living_lexicon",
)


def load_senses(path: str | Path = DEFAULT_SENSES) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    rows = []
    with file_path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            sense_id = _clean(row.get("sense_id"))
            word = _clean(row.get("word"))
            definition = _clean(row.get("definition"))
            if not sense_id or not word or not definition:
                continue
            rows.append({
                "sense_id": sense_id,
                "word": word,
                "entry_type": _clean(row.get("entry_type")) or "word",
                "part_of_speech": _clean(row.get("part_of_speech")) or None,
                "definition": definition,
                "meaning_type": _clean(row.get("meaning_type")) or "attested",
                "register": _clean(row.get("register")) or None,
                "domain": _clean(row.get("domain")) or None,
                "era_name": _clean(row.get("era_name")) or None,
                "first_attested_year": _safe_int(row.get("first_attested_year")),
                "last_attested_year": _safe_int(row.get("last_attested_year")),
                "first_attested_source": _clean(row.get("first_attested_source")) or None,
                "source_slug": _clean(row.get("source_slug")) or None,
                "confidence": _clean(row.get("confidence")) or "medium",
                "confidence_reason": _clean(row.get("confidence_reason")) or None,
                "evidence_grade": _clean(row.get("evidence_grade")).upper() or None,
                "citation": _clean(row.get("citation")) or None,
                "page": _clean(row.get("page")) or None,
                "entry_headword": _clean(row.get("entry_headword")) or None,
                "source_url": _clean(row.get("source_url")) or None,
                "access_date": _clean(row.get("access_date")) or None,
                "review_status": _clean(row.get("review_status")) or None,
                "semantic_change_type": _clean(row.get("semantic_change_type")) or None,
                "origin_status": _clean(row.get("origin_status")) or None,
                "usage_region": _clean(row.get("usage_region")) or None,
                "usage_register": _clean(row.get("usage_register")) or None,
                "notes": _clean(row.get("notes")) or None,
            })
    return rows


def load_attestations(path: str | Path = DEFAULT_ATTESTATIONS) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    rows = []
    with file_path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            sense_id = _clean(row.get("sense_id"))
            word = _clean(row.get("word"))
            if not sense_id or not word:
                continue
            rows.append({
                "sense_id": sense_id,
                "word": word,
                "quote": _clean(row.get("quote")) or None,
                "quote_year": _safe_int(row.get("quote_year")),
                "quote_author": _clean(row.get("quote_author")) or None,
                "quote_work": _clean(row.get("quote_work")) or None,
                "source_slug": _clean(row.get("source_slug")) or None,
                "attestation_type": _clean(row.get("attestation_type")) or "historical_dictionary",
                "citation": _clean(row.get("citation")) or None,
                "evidence_grade": _clean(row.get("evidence_grade")).upper() or None,
                "confidence_reason": _clean(row.get("confidence_reason")) or None,
                "page": _clean(row.get("page")) or None,
                "entry_headword": _clean(row.get("entry_headword")) or None,
                "source_url": _clean(row.get("source_url")) or None,
                "access_date": _clean(row.get("access_date")) or None,
                "review_status": _clean(row.get("review_status")) or None,
                "notes": _clean(row.get("notes")) or None,
            })
    return rows


SENSE_SQL = """
INSERT INTO senses (
    sense_id, word, entry_type, part_of_speech, definition, meaning_type,
    register, domain, era_name, first_attested_year, last_attested_year,
    first_attested_source, source_slug, confidence, confidence_reason,
    evidence_grade, citation, page, entry_headword, source_url, access_date,
    review_status, semantic_change_type, origin_status, usage_region,
    usage_register, notes
) VALUES %s
ON CONFLICT (sense_id) DO UPDATE SET
    word = EXCLUDED.word,
    entry_type = EXCLUDED.entry_type,
    part_of_speech = EXCLUDED.part_of_speech,
    definition = EXCLUDED.definition,
    meaning_type = EXCLUDED.meaning_type,
    register = EXCLUDED.register,
    domain = EXCLUDED.domain,
    era_name = EXCLUDED.era_name,
    first_attested_year = EXCLUDED.first_attested_year,
    last_attested_year = EXCLUDED.last_attested_year,
    first_attested_source = EXCLUDED.first_attested_source,
    source_slug = EXCLUDED.source_slug,
    confidence = EXCLUDED.confidence,
    confidence_reason = EXCLUDED.confidence_reason,
    evidence_grade = EXCLUDED.evidence_grade,
    citation = EXCLUDED.citation,
    page = EXCLUDED.page,
    entry_headword = EXCLUDED.entry_headword,
    source_url = EXCLUDED.source_url,
    access_date = EXCLUDED.access_date,
    review_status = EXCLUDED.review_status,
    semantic_change_type = EXCLUDED.semantic_change_type,
    origin_status = EXCLUDED.origin_status,
    usage_region = EXCLUDED.usage_region,
    usage_register = EXCLUDED.usage_register,
    notes = EXCLUDED.notes
"""

ATTESTATION_SQL = """
INSERT INTO attestations (
    sense_id, word, quote, quote_year, quote_author, quote_work,
    source_slug, attestation_type, citation, evidence_grade, confidence_reason,
    page, entry_headword, source_url, access_date, review_status, notes
) VALUES %s
"""


def import_senses_and_attestations(
    senses_path: str | Path = DEFAULT_SENSES,
    attestations_path: str | Path = DEFAULT_ATTESTATIONS,
    dry_run: bool = False,
) -> dict[str, int | bool]:
    senses = load_senses(senses_path)
    attestations = load_attestations(attestations_path)

    print(f"[senses] senses: {len(senses):,} from {senses_path}")
    print(f"[senses] attestations: {len(attestations):,} from {attestations_path}")

    if dry_run:
        for row in senses[:10]:
            print(f"  sense {row['sense_id']}: {row['word']} = {row['definition'][:70]}")
        for row in attestations[:10]:
            print(f"  attestation {row['sense_id']}: {row.get('quote_year')} {row.get('source_slug')}")
        print("  [dry_run] - no data written")
        return {"senses": len(senses), "attestations": len(attestations), "dry_run": True}

    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(SYNC_URL)
    try:
        with conn:
            with conn.cursor() as cur:
                if senses:
                    psycopg2.extras.execute_values(
                        cur,
                        SENSE_SQL,
                        [tuple(row.values()) for row in senses],
                        template=(
                            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                            "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                        ),
                    )
                if attestations:
                    psycopg2.extras.execute_values(
                        cur,
                        ATTESTATION_SQL,
                        [tuple(row.values()) for row in attestations],
                        template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    )
    finally:
        conn.close()

    print(f"[senses] Done - senses={len(senses):,}, attestations={len(attestations):,}")
    return {"senses": len(senses), "attestations": len(attestations), "dry_run": False}


if __name__ == "__main__":
    from ingestor.utils import build_arg_parser
    parser = build_arg_parser(
        description="Import historical senses and attestations.",
        include_dry_run=True,
        extra_args=[
            (["--senses"], {"default": str(DEFAULT_SENSES), "help": "Senses CSV path."}),
            (["--attestations"], {"default": str(DEFAULT_ATTESTATIONS), "help": "Attestations CSV path."}),
        ],
    )
    args = parser.parse_args()
    import_senses_and_attestations(
        senses_path=args.senses,
        attestations_path=args.attestations,
        dry_run=args.dry_run,
    )
