"""
Words Merge Importer — produces Words/english_words_master_lexicon.csv by
combining all local word sources and the dwyl/english-words list, without
duplicating any word.

Sources (highest → lowest priority):
  1. etymology_seed_database.csv           — 61 words with full etymology
  2. etymology_seed_database_v2.csv        — 80 words with full etymology
  3. Collins Scrabble Words (2019).txt     — ~279k words with definitions
  4. english_words_primary_lexicon.csv     — ~3k words, word-only
  5. dwyl/english-words (words_alpha.txt)  — ~466k words, word-only
  6. medical_terms.csv                     — ~59k clinical/pharmaceutical terms

Output CSV columns:
  word, definition, origin_language, language_family, historical_context

Usage:
  python -m ingestor.words_merge_importer
  python -m ingestor.words_merge_importer --dry-run
  python -m ingestor.words_merge_importer --no-fetch        # skip GitHub download
  python -m ingestor.words_merge_importer --output Words/custom_name.csv
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import urllib.request
from pathlib import Path
from typing import TypedDict

WORDS_DIR = Path(__file__).parent.parent / "Words"
DEFAULT_OUTPUT = WORDS_DIR / "english_words_master_lexicon.csv"

COLLINS_FILE = WORDS_DIR / "Collins Scrabble Words (2019) with definitions.txt"
PRIMARY_LEXICON = WORDS_DIR / "english_words_primary_lexicon.csv"
SEED_V1 = WORDS_DIR / "etymology_seed_database.csv"
SEED_V2 = WORDS_DIR / "etymology_seed_database_v2.csv"
MEDICAL_TERMS = WORDS_DIR / "medical_terms.csv"

DWYL_URL = "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt"
DWYL_CACHE = WORDS_DIR / "dwyl_words_alpha.txt"

OUTPUT_FIELDS = ["word", "definition", "origin_language", "language_family", "historical_context"]

# Strips scrabble bracket notation: [n -S], [v -ED, -ING, -S], [interj], etc.
_BRACKET_RE = re.compile(r"\s*\[[^\]]*\]")


class WordRecord(TypedDict):
    word: str
    definition: str
    origin_language: str
    language_family: str
    historical_context: str


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _key(word: str) -> str:
    return word.strip().lower()


def _capitalise(word: str) -> str:
    """First letter upper, rest lower — appropriate for common English words."""
    w = word.strip()
    return w[0].upper() + w[1:].lower() if w else w


def _clean_collins_definition(raw: str) -> str:
    """Strip bracket scrabble notation; normalise whitespace; keep all senses."""
    cleaned = _BRACKET_RE.sub("", raw)
    # Normalise multiple spaces and stray ' / ' separators
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\s*/\s*$", "", cleaned).strip()
    return cleaned


def _empty_record(word: str) -> WordRecord:
    return WordRecord(word=word, definition="", origin_language="", language_family="", historical_context="")


# ---------------------------------------------------------------------------
# Source loaders
# ---------------------------------------------------------------------------

def load_seed_csv(path: Path) -> dict[str, WordRecord]:
    """Load etymology_seed_database*.csv — columns: word, origin_language, language_family, historical_context."""
    records: dict[str, WordRecord] = {}
    if not path.exists():
        print(f"  [skip] {path.name} not found", file=sys.stderr)
        return records
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            word = row.get("word", "").strip()
            if not word:
                continue
            k = _key(word)
            records[k] = WordRecord(
                word=word,
                definition="",
                origin_language=row.get("origin_language", "").strip(),
                language_family=row.get("language_family", "").strip(),
                historical_context=row.get("historical_context", "").strip(),
            )
    return records


def load_primary_lexicon(path: Path) -> dict[str, WordRecord]:
    """Load english_words_primary_lexicon.csv — single column: Word."""
    records: dict[str, WordRecord] = {}
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            word = (row.get("Word") or row.get("word") or "").strip()
            if word:
                records[_key(word)] = _empty_record(word)
    return records


def load_collins(path: Path) -> dict[str, WordRecord]:
    """
    Load Collins Scrabble Words (2019).txt
    Format: WORD<TAB>DEFINITION  (first line is a file description, skip it)
    """
    records: dict[str, WordRecord] = {}
    if not path.exists():
        print(f"  [skip] Collins file not found: {path}", file=sys.stderr)
        return records

    with path.open("r", encoding="utf-8", newline="") as fh:
        first = True
        for raw_line in fh:
            line = raw_line.rstrip("\n")
            if first:
                first = False
                # Skip the description line that begins with "Collins Scrabble"
                if line.startswith("Collins"):
                    continue
            if not line.strip():
                continue

            parts = line.split("\t", 1)
            word_raw = parts[0].strip()
            if not word_raw:
                continue

            word = _capitalise(word_raw)
            definition = _clean_collins_definition(parts[1]) if len(parts) > 1 else ""

            k = _key(word)
            records[k] = WordRecord(
                word=word,
                definition=definition,
                origin_language="",
                language_family="",
                historical_context="",
            )
    return records


def load_medical_terms(path: Path) -> dict[str, WordRecord]:
    """Load medical_terms.csv — preserves exact casing (acronyms must stay uppercase)."""
    records: dict[str, WordRecord] = {}
    if not path.exists():
        print(f"  [skip] {path.name} not found — run ingestor.medical_importer first", file=sys.stderr)
        return records
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            word = row.get("word", "").strip()
            if not word:
                continue
            records[_key(word)] = WordRecord(
                word=word,
                definition=row.get("definition", "").strip(),
                origin_language=row.get("origin_language", "").strip(),
                language_family=row.get("language_family", "").strip(),
                historical_context=row.get("historical_context", "").strip(),
            )
    return records


def fetch_dwyl(cache_path: Path, skip_fetch: bool) -> dict[str, WordRecord]:
    """Fetch (or read cached) dwyl words_alpha.txt — one lowercase word per line."""
    if not cache_path.exists():
        if skip_fetch:
            print("  [skip] dwyl cache not found and --no-fetch set; skipping dwyl source.")
            return {}
        print(f"  Downloading dwyl/english-words → {cache_path.name} …")
        try:
            urllib.request.urlretrieve(DWYL_URL, cache_path)
            print("  Download complete.")
        except Exception as e:
            print(f"  [warn] Could not download dwyl words: {e}", file=sys.stderr)
            return {}
    else:
        print(f"  Using cached dwyl file: {cache_path.name}")

    records: dict[str, WordRecord] = {}
    with cache_path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            word_raw = raw.strip()
            if word_raw:
                word = _capitalise(word_raw)
                records[_key(word)] = _empty_record(word)
    return records


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

def merge_sources(
    seed_v1: dict[str, WordRecord],
    seed_v2: dict[str, WordRecord],
    collins: dict[str, WordRecord],
    primary: dict[str, WordRecord],
    dwyl: dict[str, WordRecord],
    medical: dict[str, WordRecord],
) -> dict[str, WordRecord]:
    """
    Merge all sources in priority order.
    A key present in a higher-priority source is never overwritten.
    """
    merged: dict[str, WordRecord] = {}

    for source_name, source in [
        ("seed_v1", seed_v1),
        ("seed_v2", seed_v2),
        ("collins", collins),
        ("primary", primary),
        ("dwyl", dwyl),
        ("medical", medical),
    ]:
        added = 0
        for k, record in source.items():
            if k not in merged:
                merged[k] = record
                added += 1
        print(f"  {source_name:12s}: {len(source):>7,} words   (+{added:>7,} new)")

    return merged


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

def write_output(records: dict[str, WordRecord], output: Path, dry_run: bool) -> None:
    sorted_records = sorted(records.values(), key=lambda r: _key(r["word"]))

    if dry_run:
        print(f"\n[dry_run] Would write {len(sorted_records):,} words to {output}")
        print("  Sample (first 15):")
        for r in sorted_records[:15]:
            defn = r["definition"][:60] + "…" if len(r["definition"]) > 60 else r["definition"]
            print(f"    {r['word']:<20s}  {defn}")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(sorted_records)

    print(f"\n[done] Wrote {len(sorted_records):,} words → {output}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge all word sources into english_words_master_lexicon.csv"
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output CSV path.")
    parser.add_argument("--no-fetch", action="store_true", help="Skip downloading dwyl; use local cache only.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing.")
    args = parser.parse_args()

    output = Path(args.output)
    print("=== Living Lexicon — Word Merge ===\n")

    print("[1/7] Loading etymology seed databases …")
    seed_v1 = load_seed_csv(SEED_V1)
    seed_v2 = load_seed_csv(SEED_V2)
    print(f"  seed_v1: {len(seed_v1):,} words")
    print(f"  seed_v2: {len(seed_v2):,} words")

    print("\n[2/7] Loading Collins Scrabble Words (2019) …")
    collins = load_collins(COLLINS_FILE)
    print(f"  Collins: {len(collins):,} words")

    print("\n[3/7] Loading primary lexicon …")
    primary = load_primary_lexicon(PRIMARY_LEXICON)
    print(f"  Primary: {len(primary):,} words")

    print("\n[4/7] Fetching dwyl/english-words …")
    dwyl = fetch_dwyl(DWYL_CACHE, skip_fetch=args.no_fetch)
    print(f"  dwyl:    {len(dwyl):,} words")

    print("\n[5/7] Loading medical terms …")
    medical = load_medical_terms(MEDICAL_TERMS)
    print(f"  medical: {len(medical):,} words")

    print("\n[6/7] Merging sources (higher priority wins on conflict) …")
    merged = merge_sources(seed_v1, seed_v2, collins, primary, dwyl, medical)
    print(f"\n  Total unique words: {len(merged):,}")

    # Dedup stats
    seed_total = len(set(seed_v1) | set(seed_v2))
    print(f"  Words with etymology data: {seed_total:,}")
    with_def = sum(1 for r in merged.values() if r["definition"])
    print(f"  Words with definitions:    {with_def:,}")

    print(f"\n[7/7] Writing → {output} …")
    write_output(merged, output, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
