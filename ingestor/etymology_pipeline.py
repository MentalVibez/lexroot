"""
Etymology Pipeline — coordinates three agents to enrich the master lexicon
with etymology data and writes Words/english_words_etymology.csv.

Agent priority (higher wins on conflict):
  1. etymwn     — etymwn.tsv, 6M Wiktionary-derived relations (~75% coverage)
  2. collins    — language hints from Collins definition parentheticals
  3. wiktionary — Wiktionary REST API (phonemes + etymology text, fills gaps)

Existing seed data (from etymology_seed_database*.csv) is loaded first and
never overwritten.

Usage:
  python3 -m ingestor.etymology_pipeline
  python3 -m ingestor.etymology_pipeline --skip-wiktionary   # offline / fast
  python3 -m ingestor.etymology_pipeline --dry-run           # preview only
  python3 -m ingestor.etymology_pipeline --limit 5000        # test subset
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from dataclasses import asdict
from pathlib import Path

from ingestor.etymology_agents.base import EtymologyRecord
from ingestor.etymology_agents.collins_agent import CollinsHintAgent
from ingestor.etymology_agents.etymwn_agent import EtymwnAgent
from ingestor.etymology_agents.wiktionary_agent import WiktionaryAgent

WORDS_DIR = Path(__file__).parent.parent / "Words"
MASTER_LEXICON = WORDS_DIR / "english_words_master_lexicon.csv"
SEED_V1 = WORDS_DIR / "etymology_seed_database.csv"
SEED_V2 = WORDS_DIR / "etymology_seed_database_v2.csv"
OUTPUT = WORDS_DIR / "english_words_etymology.csv"

OUTPUT_FIELDS = [
    "word", "definition", "phonemes", "etymology_root",
    "origin_language", "language_family", "historical_context",
    "confidence", "source_agent",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_master_lexicon() -> dict[str, dict]:
    """word.lower() → {word, definition, origin_language, ...}"""
    records: dict[str, dict] = {}
    with MASTER_LEXICON.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            word = row.get("word", "").strip()
            if word:
                records[word.lower()] = dict(row)
    return records


def _load_seed_records() -> dict[str, EtymologyRecord]:
    """Load seed database CSV files as high-confidence records (never overwrite)."""
    seeds: dict[str, EtymologyRecord] = {}
    for path in (SEED_V1, SEED_V2):
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                word = row.get("word", "").strip()
                if not word:
                    continue
                seeds[word.lower()] = EtymologyRecord(
                    word=word,
                    origin_language=row.get("origin_language", "").strip() or None,
                    language_family=row.get("language_family", "").strip() or None,
                    historical_context=row.get("historical_context", "").strip() or None,
                    confidence="high",
                    source_agent="seed_database",
                )
    return seeds


def _merge(
    base: EtymologyRecord,
    enrichment: EtymologyRecord,
) -> EtymologyRecord:
    """Fill empty fields in base from enrichment; never overwrite non-empty."""
    if not base.phonemes and enrichment.phonemes:
        base.phonemes = enrichment.phonemes
    if not base.etymology_root and enrichment.etymology_root:
        base.etymology_root = enrichment.etymology_root
    if not base.origin_language and enrichment.origin_language:
        base.origin_language = enrichment.origin_language
        base.language_family = enrichment.language_family
        if not base.source_agent:
            base.source_agent = enrichment.source_agent
        if enrichment.confidence in ("high", "medium") and base.confidence == "low":
            base.confidence = enrichment.confidence
    if not base.historical_context and enrichment.historical_context:
        base.historical_context = enrichment.historical_context
    return base


def _stats(records: dict[str, EtymologyRecord]) -> None:
    total = len(records)
    has_origin = sum(1 for r in records.values() if r.origin_language)
    has_root = sum(1 for r in records.values() if r.etymology_root)
    has_phonemes = sum(1 for r in records.values() if r.phonemes)
    has_context = sum(1 for r in records.values() if r.historical_context)
    print(f"  Words:              {total:>8,}")
    print(f"  Has origin:         {has_origin:>8,}  ({has_origin/total*100:.1f}%)")
    print(f"  Has etymology_root: {has_root:>8,}  ({has_root/total*100:.1f}%)")
    print(f"  Has historical_ctx: {has_context:>8,}  ({has_context/total*100:.1f}%)")
    print(f"  Has phonemes:       {has_phonemes:>8,}  ({has_phonemes/total*100:.1f}%)")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    skip_wiktionary: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
    wiktionary_limit: int | None = None,
) -> None:
    t0 = time.monotonic()
    print("=== Living Lexicon — Etymology Pipeline ===\n")

    # ── 1. Load source data ──────────────────────────────────────────────────
    print("[1/6] Loading master lexicon …")
    master = _load_master_lexicon()
    words_all = list(master.keys())
    if limit:
        words_all = words_all[:limit]
        print(f"  (limited to {limit:,} words for this run)")
    print(f"  {len(words_all):,} words loaded")

    print("\n[2/6] Loading seed database records (fixed, not overwritten) …")
    result: dict[str, EtymologyRecord] = _load_seed_records()
    print(f"  {len(result):,} seed words protected")

    # Initialise result for every word (carry definition forward)
    for key in words_all:
        if key not in result:
            row = master[key]
            result[key] = EtymologyRecord(
                word=row.get("word", key),
                origin_language=row.get("origin_language") or None,
                language_family=row.get("language_family") or None,
                historical_context=row.get("historical_context") or None,
                confidence="low",
            )

    # ── 2. etymwn agent ──────────────────────────────────────────────────────
    print("\n[3/6] Running EtymwnAgent …")
    etymwn = EtymwnAgent()
    etymwn.load()

    needs_origin = [k for k in words_all if not result[k].origin_language]
    print(f"  Looking up {len(needs_origin):,} words without origin …")
    etymwn_hits = etymwn.batch_lookup(needs_origin)
    for key, rec in etymwn_hits.items():
        result[key] = _merge(result[key], rec)
    print(f"  etymwn filled {len(etymwn_hits):,} words")

    # ── 3. Collins hint agent ────────────────────────────────────────────────
    print("\n[4/6] Running CollinsHintAgent …")
    collins = CollinsHintAgent()
    collins.load()

    needs_origin2 = [k for k in words_all if not result[k].origin_language]
    print(f"  Looking up {len(needs_origin2):,} still-missing words …")
    collins_hits = collins.batch_lookup(needs_origin2)
    for key, rec in collins_hits.items():
        result[key] = _merge(result[key], rec)
    print(f"  Collins hints filled {len(collins_hits):,} words")

    # ── 4. Wiktionary agent ──────────────────────────────────────────────────
    if not skip_wiktionary:
        print("\n[5/6] Running WiktionaryAgent (async, ~100 req/s) …")
        # Only hit Wiktionary for words still missing origin OR phonemes
        needs_wiki = [
            master[k].get("word", k)
            for k in words_all
            if not result[k].origin_language or not result[k].phonemes
        ]
        if wiktionary_limit:
            needs_wiki = needs_wiki[:wiktionary_limit]
            print(f"  (Wiktionary limited to {wiktionary_limit:,} words)")
        print(f"  {len(needs_wiki):,} words to fetch from Wiktionary …")

        wiki_agent = WiktionaryAgent()
        wiki_results = wiki_agent.run(needs_wiki)
        for word, rec in wiki_results.items():
            result[word.lower()] = _merge(result[word.lower()], rec)
        print(f"  Wiktionary filled {len(wiki_results):,} words")
    else:
        print("\n[5/6] WiktionaryAgent skipped (--skip-wiktionary)")

    # ── 5. Stats ─────────────────────────────────────────────────────────────
    print("\n[6/6] Final coverage stats:")
    _stats(result)

    elapsed = time.monotonic() - t0
    print(f"\n  Elapsed: {elapsed:.1f}s")

    if dry_run:
        print("\n[dry_run] Preview — first 15 enriched records:")
        for i, rec in enumerate(list(result.values())[:15]):
            print(f"  {rec.word:<20s}  origin={rec.origin_language or '—':<22s}  "
                  f"root={rec.etymology_root or '—':<20s}  src={rec.source_agent or '—'}")
        print("  (no file written)")
        return

    # ── 6. Write output ───────────────────────────────────────────────────────
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for key in sorted(result):
            rec = result[key]
            row = asdict(rec)
            # Carry definition forward from master lexicon
            row["definition"] = master.get(key, {}).get("definition", "")
            writer.writerow(row)

    print(f"\n[done] Wrote {len(result):,} words → {OUTPUT}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Run the etymology enrichment pipeline.")
    parser.add_argument("--skip-wiktionary", action="store_true",
                        help="Skip Wiktionary API calls (offline / fast mode).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview output without writing.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process only the first N words (for testing).")
    parser.add_argument("--wiktionary-limit", type=int, default=None,
                        help="Cap Wiktionary requests at N (useful for initial runs).")
    args = parser.parse_args()

    run_pipeline(
        skip_wiktionary=args.skip_wiktionary,
        dry_run=args.dry_run,
        limit=args.limit,
        wiktionary_limit=args.wiktionary_limit,
    )


if __name__ == "__main__":
    main()
