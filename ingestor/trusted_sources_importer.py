"""
Bulk trusted-source seeding pipeline.

This command builds the Living Lexicon in layers:
  1. curated seed data and small Words/ CSV seed databases
  2. Princeton WordNet broad modern-English headword coverage
  3. EtymWordNet etymological-origin and cognate relationships
  4. optional Kaikki/Wiktextract structured Wiktionary data
  5. optional Etymology DB structured etymology data
  6. optional GCIDE historical dictionary data
  7. optional Open English WordNet modern lexical graph data
  8. optional Wikidata Lexeme CC0 identifiers/forms/glosses
  9. optional frequency and validation metadata

It avoids direct bulk scraping of copyrighted or automation-hostile sites. Use
Etymonline, Google Scholar, OED, Brill dictionaries, and similar scholarly
sources as citation/enrichment sources when you have permission, exported data,
or manually curated entries.

Usage:
  python -m ingestor.trusted_sources_importer --dry-run
  python -m ingestor.trusted_sources_importer
"""
from __future__ import annotations

import argparse
from typing import Any

from ingestor.etymwn_importer import import_from_etymwn
from ingestor.etymology_db_importer import import_from_etymology_db
from ingestor.frequency_importer import import_frequency_metadata
from ingestor.gcide_importer import import_from_gcide
from ingestor.kaikki_importer import import_from_kaikki
from ingestor.open_english_wordnet_importer import import_from_open_english_wordnet
from ingestor.seed_data import build_seed_words, seed
from ingestor.wikidata_lexeme_importer import import_from_wikidata_lexemes
from ingestor.wordlist_validator_importer import import_validation_wordlist
from ingestor.wordnet_importer import import_from_wordnet


def import_from_trusted_sources(
    wordnet_limit: int | None = None,
    etymwn_limit: int | None = None,
    kaikki_path: str | None = None,
    kaikki_limit: int | None = 5000,
    etymology_db_path: str | None = None,
    etymology_db_limit: int | None = 5000,
    gcide_path: str | None = None,
    gcide_limit: int | None = 5000,
    oewn_path: str | None = None,
    oewn_limit: int | None = 5000,
    wikidata_lexemes_path: str | None = None,
    wikidata_lexemes_limit: int | None = 5000,
    frequency_path: str | None = None,
    frequency_source: str = "subtlex-us",
    frequency_limit: int | None = 5000,
    scowl_path: str | None = None,
    scowl_limit: int | None = 5000,
    moby_path: str | None = None,
    moby_limit: int | None = 5000,
    dry_run: bool = False,
) -> dict[str, Any]:
    if dry_run:
        seed_entries = build_seed_words()
        print(f"[trusted] Curated + Words/ CSV seed entries: {len(seed_entries)}")
        wordnet_result = import_from_wordnet(limit=wordnet_limit, dry_run=True)
        etymwn_result = import_from_etymwn(
            target_langs=["*"],
            limit=etymwn_limit,
            dry_run=True,
        )
        results: dict[str, Any] = {
            "dry_run": True,
            "seed_entries": len(seed_entries),
            "wordnet": wordnet_result,
            "etymwn": etymwn_result,
        }
        if kaikki_path:
            results["kaikki"] = import_from_kaikki(kaikki_path, limit=kaikki_limit, dry_run=True)
        if etymology_db_path:
            results["etymology_db"] = import_from_etymology_db(etymology_db_path, limit=etymology_db_limit, dry_run=True)
        if gcide_path:
            results["gcide"] = import_from_gcide(gcide_path, limit=gcide_limit, dry_run=True)
        if oewn_path:
            results["oewn"] = import_from_open_english_wordnet(oewn_path, limit=oewn_limit, dry_run=True)
        if wikidata_lexemes_path:
            results["wikidata_lexemes"] = import_from_wikidata_lexemes(
                wikidata_lexemes_path,
                limit=wikidata_lexemes_limit,
                dry_run=True,
            )
        if frequency_path:
            results["frequency"] = import_frequency_metadata(
                frequency_path,
                source_slug=frequency_source,
                limit=frequency_limit,
                dry_run=True,
            )
        if scowl_path:
            results["scowl"] = import_validation_wordlist(scowl_path, "scowl", limit=scowl_limit, dry_run=True)
        if moby_path:
            results["moby"] = import_validation_wordlist(moby_path, "moby-word-lists", limit=moby_limit, dry_run=True)
        return results

    print("[trusted] Layer 1: curated seed data + Words/ CSVs")
    seed()

    print("[trusted] Layer 2: Princeton WordNet broad headword coverage")
    wordnet_result = import_from_wordnet(limit=wordnet_limit)

    print("[trusted] Layer 3: EtymWordNet etymology relationships")
    etymwn_result = import_from_etymwn(
        target_langs=["*"],
        limit=etymwn_limit,
    )

    results = {
        "dry_run": False,
        "wordnet": wordnet_result,
        "etymwn": etymwn_result,
    }
    if kaikki_path:
        print("[trusted] Layer 4: Kaikki/Wiktextract structured Wiktionary data")
        results["kaikki"] = import_from_kaikki(kaikki_path, limit=kaikki_limit)
    if etymology_db_path:
        print("[trusted] Layer 5: Etymology DB structured etymology data")
        results["etymology_db"] = import_from_etymology_db(etymology_db_path, limit=etymology_db_limit)
    if gcide_path:
        print("[trusted] Layer 6: GCIDE historical dictionary data")
        results["gcide"] = import_from_gcide(gcide_path, limit=gcide_limit)
    if oewn_path:
        print("[trusted] Layer 7: Open English WordNet modern lexical graph data")
        results["oewn"] = import_from_open_english_wordnet(oewn_path, limit=oewn_limit)
    if wikidata_lexemes_path:
        print("[trusted] Layer 8: Wikidata Lexeme identifiers/forms/glosses")
        results["wikidata_lexemes"] = import_from_wikidata_lexemes(
            wikidata_lexemes_path,
            limit=wikidata_lexemes_limit,
        )
    if frequency_path:
        print("[trusted] Layer 9: frequency metadata")
        results["frequency"] = import_frequency_metadata(
            frequency_path,
            source_slug=frequency_source,
            limit=frequency_limit,
        )
    if scowl_path:
        print("[trusted] Layer 10: SCOWL validation word list")
        results["scowl"] = import_validation_wordlist(scowl_path, "scowl", limit=scowl_limit)
    if moby_path:
        print("[trusted] Layer 11: Moby validation word list")
        results["moby"] = import_validation_wordlist(moby_path, "moby-word-lists", limit=moby_limit)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk-import trusted local lexical and etymology sources.")
    parser.add_argument("--wordnet-limit", type=int, default=0, help="Max WordNet terms. Use 0 for no limit.")
    parser.add_argument("--etymwn-limit", type=int, default=0, help="Max EtymWordNet derivations. Use 0 for no limit.")
    parser.add_argument("--kaikki-path", help="Optional path to Kaikki/Wiktextract JSON, JSONL, or JSONL.GZ.")
    parser.add_argument("--kaikki-limit", type=int, default=5000, help="Max Kaikki entries. Use 0 for no limit.")
    parser.add_argument("--etymology-db-path", help="Optional path to Etymology DB CSV/TSV, optionally .gz.")
    parser.add_argument("--etymology-db-limit", type=int, default=5000, help="Max Etymology DB entries. Use 0 for no limit.")
    parser.add_argument("--gcide-path", help="Optional path to GCIDE tagged text/XML.")
    parser.add_argument("--gcide-limit", type=int, default=5000, help="Max GCIDE entries. Use 0 for no limit.")
    parser.add_argument("--oewn-path", help="Optional path to Open English WordNet XML or ZIP.")
    parser.add_argument("--oewn-limit", type=int, default=5000, help="Max Open English WordNet entries. Use 0 for no limit.")
    parser.add_argument("--wikidata-lexemes-path", help="Optional path to Wikidata Lexeme JSON, JSONL, or JSONL.GZ.")
    parser.add_argument("--wikidata-lexemes-limit", type=int, default=5000, help="Max Wikidata Lexeme entries. Use 0 for no limit.")
    parser.add_argument("--frequency-path", help="Optional path to SUBTLEX/wordfreq-style CSV, TSV, JSON, or JSONL.")
    parser.add_argument("--frequency-source", default="subtlex-us", choices=["subtlex-us", "wordfreq"], help="Frequency source slug.")
    parser.add_argument("--frequency-limit", type=int, default=5000, help="Max frequency records. Use 0 for no limit.")
    parser.add_argument("--scowl-path", help="Optional path to SCOWL word-list text file.")
    parser.add_argument("--scowl-limit", type=int, default=5000, help="Max SCOWL words. Use 0 for no limit.")
    parser.add_argument("--moby-path", help="Optional path to Moby word-list text file.")
    parser.add_argument("--moby-limit", type=int, default=5000, help="Max Moby words. Use 0 for no limit.")
    parser.add_argument("--dry-run", action="store_true", help="Preview counts without writing to Neo4j.")
    args = parser.parse_args()

    import_from_trusted_sources(
        wordnet_limit=None if args.wordnet_limit == 0 else args.wordnet_limit,
        etymwn_limit=None if args.etymwn_limit == 0 else args.etymwn_limit,
        kaikki_path=args.kaikki_path,
        kaikki_limit=None if args.kaikki_limit == 0 else args.kaikki_limit,
        etymology_db_path=args.etymology_db_path,
        etymology_db_limit=None if args.etymology_db_limit == 0 else args.etymology_db_limit,
        gcide_path=args.gcide_path,
        gcide_limit=None if args.gcide_limit == 0 else args.gcide_limit,
        oewn_path=args.oewn_path,
        oewn_limit=None if args.oewn_limit == 0 else args.oewn_limit,
        wikidata_lexemes_path=args.wikidata_lexemes_path,
        wikidata_lexemes_limit=None if args.wikidata_lexemes_limit == 0 else args.wikidata_lexemes_limit,
        frequency_path=args.frequency_path,
        frequency_source=args.frequency_source,
        frequency_limit=None if args.frequency_limit == 0 else args.frequency_limit,
        scowl_path=args.scowl_path,
        scowl_limit=None if args.scowl_limit == 0 else args.scowl_limit,
        moby_path=args.moby_path,
        moby_limit=None if args.moby_limit == 0 else args.moby_limit,
        dry_run=args.dry_run,
    )
