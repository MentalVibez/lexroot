"""
Build a single clean lexicon import file from generated word data and curated
phrase/idiom sources.

Output:
  Words/build/lexicon_import.csv

Usage:
  python3 -m ingestor.lexicon_build_importer
  python3 -m ingestor.lexicon_build_importer --dry-run
  python3 -m ingestor.lexicon_build_importer --words Words/english_words_etymology.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


WORDS_DIR = Path(__file__).parent.parent / "Words"
DEFAULT_WORDS = WORDS_DIR / "english_words_etymology.csv"
FALLBACK_WORDS = WORDS_DIR / "english_words_master_lexicon.csv"
DEFAULT_DEFINITIONS = WORDS_DIR / "open_definitions.csv"
DEFAULT_MEDICAL = WORDS_DIR / "medical_terms.csv"
DEFAULT_IDIOMS = WORDS_DIR / "sources" / "idioms.csv"
DEFAULT_OUTPUT = WORDS_DIR / "build" / "lexicon_import.csv"
DEFAULT_REJECTED = WORDS_DIR / "build" / "rejected_entries.csv"

OUTPUT_FIELDS = [
    "entry",
    "entry_type",
    "definition",
    "definition_source_slug",
    "definition_source_name",
    "definition_license",
    "phonemes",
    "etymology_root",
    "origin_language",
    "language_family",
    "historical_context",
    "confidence",
    "source_agent",
    "literal_meaning",
    "figurative_meaning",
    "example_usage",
    "origin_theory",
    "origin_theory_status",
    "earliest_known_use_year",
    "earliest_known_use_source",
    "evidence_grade",
    "confidence_reason",
    "citation",
    "page",
    "entry_headword",
    "source_url",
    "access_date",
    "review_status",
    "semantic_drift_history",
]


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _key(entry: str, entry_type: str) -> tuple[str, str]:
    return (_clean(entry).casefold(), _clean(entry_type).casefold() or "word")


def _era_record(row: dict[str, str]) -> dict | None:
    era_name = _clean(row.get("era_name"))
    meaning = _clean(row.get("meaning"))
    if not era_name and not meaning:
        return None

    def safe_int(value: str | None) -> int | None:
        try:
            return int(_clean(value))
        except ValueError:
            return None

    return {
        "era_name": era_name or "Modern English",
        "start_year": safe_int(row.get("start_year")),
        "end_year": safe_int(row.get("end_year")),
        "meaning": meaning or None,
        "usage_example": _clean(row.get("usage_example")) or _clean(row.get("example_usage")) or None,
        "source_slug": _clean(row.get("source_slug")) or None,
        "confidence": _clean(row.get("confidence")) or None,
        "evidence_grade": _clean(row.get("evidence_grade")).upper() or None,
        "confidence_reason": _clean(row.get("confidence_reason")) or None,
        "citation": _clean(row.get("citation")) or None,
        "page": _clean(row.get("page")) or None,
        "entry_headword": _clean(row.get("entry_headword")) or None,
        "review_status": _clean(row.get("review_status")) or None,
        "notes": _clean(row.get("notes")) or None,
    }


def _normalise_row(row: dict[str, str], default_type: str) -> dict[str, str]:
    entry = _clean(row.get("entry")) or _clean(row.get("word")) or _clean(row.get("Word"))
    entry_type = _clean(row.get("entry_type")) or default_type
    default_definition_source = "medical_terms" if default_type == "medical_term" and _clean(row.get("definition")) else ""
    drift = _clean(row.get("semantic_drift_history"))
    if not drift:
        era = _era_record(row)
        drift = json.dumps([era], ensure_ascii=False) if era else ""

    return {
        "entry": entry,
        "entry_type": entry_type,
        "definition": _clean(row.get("definition")),
        "definition_source_slug": _clean(row.get("definition_source_slug")) or _clean(row.get("source_slug")) or default_definition_source,
        "definition_source_name": _clean(row.get("definition_source_name")),
        "definition_license": _clean(row.get("definition_license")),
        "phonemes": _clean(row.get("phonemes")),
        "etymology_root": _clean(row.get("etymology_root")),
        "origin_language": _clean(row.get("origin_language")),
        "language_family": _clean(row.get("language_family")),
        "historical_context": _clean(row.get("historical_context")),
        "confidence": _clean(row.get("confidence")),
        "source_agent": _clean(row.get("source_agent")) or _clean(row.get("source_slug")),
        "literal_meaning": _clean(row.get("literal_meaning")),
        "figurative_meaning": _clean(row.get("figurative_meaning")),
        "example_usage": _clean(row.get("example_usage")),
        "origin_theory": _clean(row.get("origin_theory")),
        "origin_theory_status": _clean(row.get("origin_theory_status")),
        "earliest_known_use_year": _clean(row.get("earliest_known_use_year")),
        "earliest_known_use_source": _clean(row.get("earliest_known_use_source")),
        "evidence_grade": _clean(row.get("evidence_grade")).upper(),
        "confidence_reason": _clean(row.get("confidence_reason")),
        "citation": _clean(row.get("citation")),
        "page": _clean(row.get("page")),
        "entry_headword": _clean(row.get("entry_headword")),
        "source_url": _clean(row.get("source_url")),
        "access_date": _clean(row.get("access_date")),
        "review_status": _clean(row.get("review_status")),
        "semantic_drift_history": drift,
    }


def load_source(path: Path, default_type: str) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    records: dict[tuple[str, str], dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            record = _normalise_row(row, default_type)
            if record["entry"]:
                records[_key(record["entry"], record["entry_type"])] = record
    return records


def load_definition_overlay(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    definitions: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            entry = _clean(row.get("word")) or _clean(row.get("entry"))
            definition = _clean(row.get("definition"))
            if entry and definition:
                definitions[entry.casefold()] = {
                    "definition": definition,
                    "definition_source_slug": _clean(row.get("definition_source_slug")) or "open_definitions",
                    "definition_source_name": _clean(row.get("definition_source_name")) or "Open Definitions",
                    "definition_license": _clean(row.get("definition_license")),
                }
    return definitions


def apply_definition_overlay(records: dict, definitions: dict[str, dict[str, str]]) -> int:
    filled = 0
    for record in records.values():
        if record.get("definition"):
            continue
        overlay = definitions.get(record["entry"].casefold())
        if overlay:
            record["definition"] = overlay["definition"]
            record["definition_source_slug"] = overlay["definition_source_slug"]
            record["definition_source_name"] = overlay["definition_source_name"]
            record["definition_license"] = overlay["definition_license"]
            record["source_agent"] = record.get("source_agent") or "open_definitions"
            filled += 1
    return filled


MEDICAL_HINTS = re.compile(
    r"\b("
    r"ablation|acarbose|acromegaly|acupuncture|adenectomy|adenoidectomy|"
    r"adrenalectomy|agranulocytosis|allograft|amniocentesis|amniotomy|"
    r"anaemia|anemia|angioma|angioplasty|appendectomy|aromatherapy|"
    r"arteriotomy|arthrodesis|carcinoma|clinical|diabetes|diagnos(?:is|tic)|"
    r"disorder|fracture|humerus|injury|lesion|malignant|neoplasm|pregnancy|"
    r"pharmaceutical|syndrome|surgical|therapy"
    r")\b",
    flags=re.I,
)


def reclassify_medical_like_words(records: dict) -> int:
    changed = 0
    for record in records.values():
        if record.get("entry_type") != "word":
            continue
        haystack = f"{record.get('entry', '')} {record.get('definition', '')}"
        if MEDICAL_HINTS.search(haystack):
            record["entry_type"] = "medical_term"
            record["source_agent"] = record.get("source_agent") or "medical_inferred"
            changed += 1
    return changed


def drop_missing_definition_records(records: dict) -> list[dict[str, str]]:
    missing_keys = [
        key for key, record in records.items()
        if not record.get("definition")
    ]
    rejected = []
    for key in missing_keys:
        record = records.pop(key)
        rejected.append({
            "entry": record.get("entry", ""),
            "entry_type": record.get("entry_type", ""),
            "reason": "missing_definition_after_open_definition_overlay",
            "source_agent": record.get("source_agent", ""),
            "origin_language": record.get("origin_language", ""),
            "etymology_root": record.get("etymology_root", ""),
        })
    return rejected


def merge_sources(words: dict, medical: dict, idioms: dict) -> dict:
    merged = dict(words)
    entry_index = {key[0]: key for key in merged}
    for key, record in medical.items():
        existing_key = entry_index.get(key[0])
        existing = merged.pop(existing_key) if existing_key else None
        record["source_agent"] = record.get("source_agent") or "medical_terms"
        if existing:
            existing["entry_type"] = "medical_term"
            for field in ("definition", "origin_language", "language_family", "historical_context"):
                if record.get(field) and not existing.get(field):
                    existing[field] = record[field]
            existing["source_agent"] = existing.get("source_agent") or "medical_terms"
            merged[key] = existing
        else:
            merged[key] = record
        entry_index[key[0]] = key
    for key, record in idioms.items():
        existing_key = entry_index.get(key[0])
        if existing_key:
            merged.pop(existing_key)
        merged[key] = record
        entry_index[key[0]] = key
    return merged


def write_output(records: dict, output: Path, dry_run: bool) -> None:
    rows = sorted(records.values(), key=lambda r: (r["entry_type"], r["entry"].casefold()))
    if dry_run:
        print(f"[dry-run] Would write {len(rows):,} entries to {output}")
        for row in rows[:15]:
            print(f"  {row['entry_type']:<12s} {row['entry']}")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[build] Wrote {len(rows):,} entries -> {output}")


def write_rejected_output(rejected: list[dict[str, str]], output: Path, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] Would write {len(rejected):,} rejected entries to {output}")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "entry",
                "entry_type",
                "reason",
                "source_agent",
                "origin_language",
                "etymology_root",
            ],
        )
        writer.writeheader()
        writer.writerows(sorted(rejected, key=lambda r: (r["entry_type"], r["entry"].casefold())))
    print(f"[build] Wrote {len(rejected):,} rejected entries -> {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the clean Living Lexicon import CSV.")
    parser.add_argument("--words", default=str(DEFAULT_WORDS), help="Generated/enriched words CSV.")
    parser.add_argument("--definitions", default=str(DEFAULT_DEFINITIONS), help="Open definition overlay CSV.")
    parser.add_argument("--medical", default=str(DEFAULT_MEDICAL), help="Medical term supplement CSV.")
    parser.add_argument("--idioms", default=str(DEFAULT_IDIOMS), help="Curated idioms CSV.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output import CSV.")
    parser.add_argument("--rejected-output", default=str(DEFAULT_REJECTED), help="Rejected entries CSV path.")
    parser.add_argument(
        "--keep-missing-definitions",
        action="store_true",
        help="Keep entries with blank definitions in the clean DB feed.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing.")
    args = parser.parse_args()

    words_path = Path(args.words)
    if not words_path.exists() and words_path == DEFAULT_WORDS:
        words_path = FALLBACK_WORDS

    words = load_source(words_path, "word")
    definitions = load_definition_overlay(Path(args.definitions))
    medical = load_source(Path(args.medical), "medical_term")
    idioms = load_source(Path(args.idioms), "idiom")
    merged = merge_sources(words, medical, idioms)
    filled = apply_definition_overlay(merged, definitions)
    reclassified = reclassify_medical_like_words(merged)
    rejected = [] if args.keep_missing_definitions else drop_missing_definition_records(merged)

    print(f"[build] words:  {len(words):,} from {words_path}")
    print(f"[build] defs:   {len(definitions):,} from {args.definitions}")
    print(f"[build] medical:{len(medical):,} from {args.medical}")
    print(f"[build] idioms: {len(idioms):,} from {args.idioms}")
    print(f"[build] filled missing definitions: {filled:,}")
    print(f"[build] reclassified medical-like words: {reclassified:,}")
    print(f"[build] dropped entries still missing definitions: {len(rejected):,}")
    print(f"[build] total:  {len(merged):,}")

    write_output(merged, Path(args.output), dry_run=args.dry_run)
    write_rejected_output(rejected, Path(args.rejected_output), dry_run=args.dry_run)


if __name__ == "__main__":
    main()
