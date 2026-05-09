"""
Etymology DB importer.

Consumes local CSV/TSV exports from https://github.com/droher/etymology-db.
The project has published multiple table shapes over time, so this importer is
schema-tolerant: it looks for source/target term, language, and relation columns
using common aliases, then imports English target derivations and English related
terms into the existing WordEntry model.

Usage:
  python -m ingestor.etymology_db_importer --path Words/etymology-db.csv.gz --limit 1000 --dry-run
  python -m ingestor.etymology_db_importer --path Words/etymology-db.tsv --limit 0
"""
from __future__ import annotations

import argparse
import csv
import gzip
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from ingestor.graph_loader import EtymologyClaim, LexiconIngestor, WordEntry
from ingestor.sources_catalog import ALL_SOURCES


ETYMOLOGY_DB_SOURCE_SLUG = "etymology-db"
_WORD = re.compile(r"^[a-z][a-z'\-]{1,79}$")

SOURCE_WORD_KEYS = ["source_term", "source_word", "source", "from_term", "from_word", "parent_term", "term1"]
SOURCE_LANG_KEYS = ["source_lang", "source_language", "from_lang", "from_language", "parent_lang", "lang1"]
TARGET_WORD_KEYS = ["target_term", "target_word", "target", "to_term", "to_word", "child_term", "term2", "term", "word"]
TARGET_LANG_KEYS = ["target_lang", "target_language", "to_lang", "to_language", "child_lang", "lang2", "language", "lang"]
RELATION_KEYS = ["relation", "rel", "relationship", "type", "reltype"]

LANGUAGE_NAMES = {
    "en": "English",
    "eng": "English",
    "la": "Classical Latin",
    "lat": "Classical Latin",
    "grc": "Ancient Greek",
    "ang": "Old English",
    "enm": "Middle English",
    "fro": "Old French",
    "fr": "French",
    "fra": "French",
    "de": "German",
    "deu": "German",
    "ar": "Arabic",
    "ara": "Arabic",
    "he": "Hebrew",
    "heb": "Hebrew",
    "san": "Sanskrit",
    "ine": "Proto-Indo-European",
    "pie": "Proto-Indo-European",
}

DERIVATION_RELATIONS = {
    "etymological_origin_of",
    "origin_of",
    "derived",
    "derived_from",
    "derives_from",
    "borrowed_from",
    "inherited_from",
    "compound",
    "root",
}
RELATED_RELATIONS = {"related", "etymologically_related", "cognate", "doublet"}


def _open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def _get(row: dict[str, Any], keys: list[str]) -> str:
    normalized = {str(k).strip().lower(): v for k, v in row.items()}
    for key in keys:
        value = normalized.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _normalize_word(value: str) -> str:
    value = re.sub(r"^\w+:\s*", "", value.strip())
    value = value.strip("*[]'\".,;:()").replace("_", " ")
    value = re.sub(r"\s+", " ", value).casefold()
    return value


def _language_name(code: str) -> str:
    code = code.strip().casefold()
    return LANGUAGE_NAMES.get(code, f"ISO 639: {code}" if code else "Unknown")


def _is_english(code: str) -> bool:
    return code.strip().casefold() in {"en", "eng", "english"}


def _is_word(value: str) -> bool:
    return bool(_WORD.match(value))


def _relation_kind(value: str) -> str:
    value = value.strip().casefold().replace("rel:", "")
    value = value.replace("-", "_").replace(" ", "_")
    if value in RELATED_RELATIONS:
        return "related"
    if value in DERIVATION_RELATIONS or "origin" in value or "derived" in value or "borrowed" in value:
        return "derivation"
    return "derivation"


def _iter_rows(path: Path) -> Iterable[dict[str, Any]]:
    delimiter = "\t" if path.suffixes[-2:] == [".tsv", ".gz"] or path.suffix == ".tsv" else ","
    with _open_text(path) as stream:
        reader = csv.DictReader(stream, delimiter=delimiter)
        for row in reader:
            yield dict(row)


def load_etymology_db_entries(path: str | Path, limit: int | None = 5000) -> list[WordEntry]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Etymology DB file not found: {file_path}")

    roots_by_word: dict[str, list[dict[str, str]]] = defaultdict(list)
    cognates: dict[str, set[str]] = defaultdict(set)

    for row in _iter_rows(file_path):
        source_word = _normalize_word(_get(row, SOURCE_WORD_KEYS))
        target_word = _normalize_word(_get(row, TARGET_WORD_KEYS))
        source_lang = _get(row, SOURCE_LANG_KEYS)
        target_lang = _get(row, TARGET_LANG_KEYS)
        relation = _relation_kind(_get(row, RELATION_KEYS))

        if not source_word or not target_word:
            continue

        if relation == "related" and _is_english(source_lang) and _is_english(target_lang):
            if _is_word(source_word) and _is_word(target_word) and source_word != target_word:
                cognates[source_word].add(target_word)
                cognates[target_word].add(source_word)
            continue

        if not _is_english(target_lang) or not _is_word(target_word):
            continue
        if not _is_word(source_word):
            continue

        roots_by_word[target_word].append({
            "root": source_word,
            "language": _language_name(source_lang),
        })
        if limit is not None and len(roots_by_word) >= limit:
            break

    entries: list[WordEntry] = []
    priority = {
        "Proto-Indo-European": 0,
        "Classical Latin": 1,
        "Ancient Greek": 2,
        "Old English": 3,
        "Middle English": 4,
        "Old French": 5,
    }
    for word, roots in roots_by_word.items():
        best = min(roots, key=lambda item: priority.get(item["language"], 99))
        entries.append(WordEntry(
            name=word,
            language="English",
            definition=f"(Etymology DB lexical entry; definition pending enrichment)",
            root_name=best["root"],
            root_meaning="Etymology DB derived relationship; root meaning pending enrichment",
            root_origin_language=best["language"],
            cognates=sorted(cognates.get(word, set()))[:10],
            etymology_claims=[
                EtymologyClaim(
                    source_form=best["root"],
                    source_language=best["language"],
                    relation_type="derived_from",
                    source_slug=ETYMOLOGY_DB_SOURCE_SLUG,
                    confidence="medium",
                    note="Structured Etymology DB relationship generated from Wiktionary-derived data.",
                    is_reconstructed=best["language"].startswith("Proto-") or best["root"].startswith("*"),
                )
            ],
            era_meanings=[
                {
                    "era_name": "Modern English",
                    "meaning": f"Etymology DB derives '{word}' from '{best['root']}'.",
                    "usage_example": None,
                    "register": "general",
                    "source": ETYMOLOGY_DB_SOURCE_SLUG,
                    "confidence": "medium",
                }
            ],
        ))
    return entries


def _register_source(ingestor: LexiconIngestor) -> None:
    for source in ALL_SOURCES:
        if source["slug"] == ETYMOLOGY_DB_SOURCE_SLUG:
            ingestor.ingest_source(source)
            return
    raise RuntimeError(f"Source '{ETYMOLOGY_DB_SOURCE_SLUG}' is not in ALL_SOURCES")


def import_from_etymology_db(path: str | Path, limit: int | None = 5000, dry_run: bool = False) -> dict[str, Any]:
    print(f"[etymology-db] Loading {path}...")
    entries = load_etymology_db_entries(path, limit=limit)
    print(f"[etymology-db] Built {len(entries)} WordEntry objects")

    if dry_run:
        for entry in entries[:10]:
            print(f"  {entry.name} <- {entry.root_name} ({entry.root_origin_language})")
        print("  [dry_run] — no data written")
        return {"entries": len(entries), "dry_run": True}

    ingestor = LexiconIngestor()
    ingestor.ensure_indexes()
    _register_source(ingestor)
    results = ingestor.bulk_ingest(entries)
    for entry in entries:
        try:
            ingestor.write_attested_in(entry.name, entry.language, ETYMOLOGY_DB_SOURCE_SLUG)
        except Exception:
            pass
    ingestor.close()
    print(f"[etymology-db] Done — ingested={results['ingested']}, failed={results['failed']}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Etymology DB CSV/TSV exports into the Living Lexicon.")
    parser.add_argument("--path", required=True, help="Path to Etymology DB CSV/TSV, optionally .gz.")
    parser.add_argument("--limit", type=int, default=5000, help="Max English entries. Use 0 for no limit.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and preview without writing to Neo4j.")
    args = parser.parse_args()

    import_from_etymology_db(
        path=args.path,
        limit=None if args.limit == 0 else args.limit,
        dry_run=args.dry_run,
    )
