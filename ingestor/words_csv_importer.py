"""
Words CSV Importer — bulk-loads a CSV into the PostgreSQL `words` table.

Expected CSV columns (all optional except 'word'/'Word'/'entry'):
  entry, entry_type, word, phonemes, etymology_root,
  definition, definition_source_slug, definition_source_name, definition_license,
  origin_language, language_family, historical_context,
  literal_meaning, figurative_meaning, example_usage,
  semantic_drift_history  (raw JSON string  -OR-  use the structured columns below)
  -- structured columns that build semantic_drift_history automatically:
  era_name, start_year, end_year, meaning, usage_example, source_slug, confidence,
  evidence_grade, confidence_reason, citation, page, entry_headword, review_status

Run both CSVs sequentially to union enrichment data; COALESCE preserves existing
values when a later CSV has NULL for a column.

Usage:
  python -m ingestor.words_csv_importer --path Words/english_words_master_lexicon.csv
  python -m ingestor.words_csv_importer --path Words/english_words_etymology.csv
  python -m ingestor.words_csv_importer --path Words/english_words_master_lexicon.csv --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

SYNC_URL: str = os.getenv(
    "POSTGRES_SYNC_URL",
    "postgresql://lexicon:lexicon_secret@localhost:5432/living_lexicon",
)

DEFAULT_BATCH = 1_000
WORDS_DIR = Path(__file__).parent.parent / "Words"


# ---------------------------------------------------------------------------
# Row parsing helpers
# ---------------------------------------------------------------------------

def _normalise_key(row: dict) -> str | None:
    """Return the entry string, tolerating newer and legacy column names."""
    return (row.get("entry") or row.get("word") or row.get("Word") or "").strip() or None


def build_drift_record(row: dict[str, str]) -> dict[str, Any] | None:
    """
    TODO — YOUR CONTRIBUTION:
    Transform a single CSV row into one semantic drift history entry (or None
    to skip). The returned dict should be serialisable to JSON and align with
    living_lexicon.models.EraRecord:

        {
            "era_name":     str,          # e.g. "Old English"
            "start_year":   int | None,   # e.g. 450
            "end_year":     int | None,   # e.g. 1150
            "meaning":      str | None,
            "usage_example": str | None,
            "source_slug":  str | None,
            "confidence":   str | None,
            "notes":        str | None,
        }

    Trade-offs to consider:
    - Return None  →  word gets imported with an empty drift history (safe default)
    - Return a record only when era_name is present  →  sparse but precise
    - Always return a stub record  →  every word has at least one history entry,
      easier to query but noisier

    The row dict contains the raw CSV headers as keys. Columns typically
    available in the primary lexicon: 'word', and potentially 'origin_language',
    'language_family', 'historical_context', 'era_name', 'start_year', 'end_year',
    'meaning', 'usage_example'.
    """
    era_name = row.get("era_name", "").strip()
    if not era_name:
        return None

    def _safe_int(val: str) -> int | None:
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    return {
        "era_name": era_name,
        "start_year": _safe_int(row.get("start_year", "")),
        "end_year": _safe_int(row.get("end_year", "")),
        "meaning": row.get("meaning", "").strip() or None,
        "usage_example": row.get("usage_example", "").strip() or None,
        "source_slug": row.get("source_slug", "").strip() or None,
        "confidence": row.get("confidence", "").strip() or None,
        "evidence_grade": row.get("evidence_grade", "").strip().upper() or None,
        "confidence_reason": row.get("confidence_reason", "").strip() or None,
        "citation": row.get("citation", "").strip() or None,
        "page": row.get("page", "").strip() or None,
        "entry_headword": row.get("entry_headword", "").strip() or None,
        "review_status": row.get("review_status", "").strip() or None,
        "notes": row.get("notes", "").strip() or None,
    }


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------

def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [r for r in csv.DictReader(fh) if _normalise_key(r)]


def parse_rows(
    raw_rows: list[dict[str, str]],
) -> list[tuple]:
    """Return tuples aligned with UPSERT_SQL."""
    seen: set[str] = set()
    out = []

    for row in raw_rows:
        word = _normalise_key(row)
        if not word or word in seen:
            continue
        seen.add(word)

        entry_type = row.get("entry_type", "").strip() or "word"
        phonemes = row.get("phonemes", "").strip() or None
        etymology_root = row.get("etymology_root", "").strip() or None
        definition = row.get("definition", "").strip() or None
        definition_source_slug = row.get("definition_source_slug", "").strip() or None
        definition_source_name = row.get("definition_source_name", "").strip() or None
        definition_license = row.get("definition_license", "").strip() or None
        origin_language = row.get("origin_language", "").strip() or None
        language_family = row.get("language_family", "").strip() or None
        historical_context = row.get("historical_context", "").strip() or None
        literal_meaning = row.get("literal_meaning", "").strip() or None
        figurative_meaning = row.get("figurative_meaning", "").strip() or None
        example_usage = row.get("example_usage", "").strip() or None

        # semantic_drift_history: prefer pre-serialised JSON column, else build
        raw_json = row.get("semantic_drift_history", "").strip()
        if raw_json:
            try:
                drift = json.loads(raw_json)
                if not isinstance(drift, list):
                    drift = [drift]
            except json.JSONDecodeError:
                drift = None
        else:
            entry = build_drift_record(row)
            drift = [entry] if entry else None

        out.append((
            word, entry_type, phonemes, etymology_root,
            definition, definition_source_slug, definition_source_name, definition_license,
            origin_language, language_family, historical_context,
            literal_meaning, figurative_meaning, example_usage,
            json.dumps(drift) if drift else None,
        ))

    return out


# ---------------------------------------------------------------------------
# Bulk insert
# ---------------------------------------------------------------------------

UPSERT_SQL = """
INSERT INTO words (word, entry_type, phonemes, etymology_root,
                   definition, definition_source_slug, definition_source_name, definition_license,
                   origin_language, language_family, historical_context,
                   literal_meaning, figurative_meaning, example_usage,
                   semantic_drift_history)
VALUES %s
ON CONFLICT (word) DO UPDATE SET
    entry_type          = COALESCE(EXCLUDED.entry_type,          words.entry_type),
    phonemes            = COALESCE(EXCLUDED.phonemes,            words.phonemes),
    etymology_root      = COALESCE(EXCLUDED.etymology_root,      words.etymology_root),
    definition          = COALESCE(EXCLUDED.definition,          words.definition),
    definition_source_slug = COALESCE(EXCLUDED.definition_source_slug, words.definition_source_slug),
    definition_source_name = COALESCE(EXCLUDED.definition_source_name, words.definition_source_name),
    definition_license  = COALESCE(EXCLUDED.definition_license,  words.definition_license),
    origin_language     = COALESCE(EXCLUDED.origin_language,     words.origin_language),
    language_family     = COALESCE(EXCLUDED.language_family,     words.language_family),
    historical_context  = COALESCE(EXCLUDED.historical_context,  words.historical_context),
    literal_meaning     = COALESCE(EXCLUDED.literal_meaning,     words.literal_meaning),
    figurative_meaning  = COALESCE(EXCLUDED.figurative_meaning,  words.figurative_meaning),
    example_usage       = COALESCE(EXCLUDED.example_usage,       words.example_usage),
    semantic_drift_history = COALESCE(EXCLUDED.semantic_drift_history, words.semantic_drift_history)
"""


def bulk_import(
    rows: list[tuple],
    batch_size: int = DEFAULT_BATCH,
    dry_run: bool = False,
) -> dict[str, int]:
    if dry_run:
        print(f"  [dry_run] would import {len(rows)} rows (first 10 shown):")
        for r in rows[:10]:
            defn = (r[4] or "")[:60]
            print(f"    entry={r[0]!r}  type={r[1]!r}  phonemes={r[2]!r}  definition={defn!r}  source={r[5]!r}  drift={'yes' if r[14] else 'no'}")
        return {"total": len(rows), "imported": 0, "dry_run": True}

    conn = psycopg2.connect(SYNC_URL)
    try:
        with conn:
            with conn.cursor() as cur:
                imported = 0
                for start in range(0, len(rows), batch_size):
                    batch = rows[start : start + batch_size]
                    psycopg2.extras.execute_values(
                        cur,
                        UPSERT_SQL,
                        batch,
                        template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
                        page_size=batch_size,
                    )
                    imported += len(batch)
                    pct = imported / len(rows) * 100
                    print(f"\r  progress: {imported:,}/{len(rows):,}  ({pct:.1f}%)", end="", flush=True)
        print()  # newline after progress
    finally:
        conn.close()

    return {"total": len(rows), "imported": imported, "dry_run": False}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk-import a words CSV into PostgreSQL.")
    parser.add_argument("--path", required=True, help="Path to the CSV file.")
    parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH,
        help=f"Rows per INSERT batch (default {DEFAULT_BATCH}).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse only; do not write.")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        print(f"[importer] ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    print(f"[importer] Reading {path} …")
    raw = load_csv(path)
    print(f"[importer] Parsed {len(raw):,} raw rows")

    rows = parse_rows(raw)
    print(f"[importer] {len(rows):,} unique entries ready for import")

    result = bulk_import(rows, batch_size=args.batch_size, dry_run=args.dry_run)

    if result["dry_run"]:
        print("[importer] Dry run complete — no data written.")
    else:
        print(f"[importer] Done — {result['imported']:,} rows upserted.")


if __name__ == "__main__":
    main()
