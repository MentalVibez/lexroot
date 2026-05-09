"""
Kaikki/Wiktextract importer.

Consumes local JSONL/JSON exports from kaikki.org / wiktextract. The importer is
tolerant of partial records and only maps fields that fit the Living Lexicon
graph: headword, modern definition, etymology text, related terms, and source
citation. Wiktionary-derived content carries share-alike attribution duties.

Usage:
  python -m ingestor.kaikki_importer --path Words/kaikki-en.jsonl --limit 1000 --dry-run
  python -m ingestor.kaikki_importer --path Words/kaikki-en.jsonl.gz --limit 0
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
from pathlib import Path
from typing import Any, Iterable

from ingestor.graph_loader import EtymologyClaim, LexiconIngestor, WordEntry
from ingestor.sources_catalog import ALL_SOURCES


KAIKKI_SOURCE_SLUG = "kaikki-wiktextract"
_SIMPLE_WORD = re.compile(r"^[a-z][a-z' -]{1,79}$")
_ROOT_PATTERNS = [
    (re.compile(r"\bfrom (?:Proto-Indo-European|PIE) \*?([A-Za-z][A-Za-z'\-]*)", re.I), "Proto-Indo-European"),
    (re.compile(r"\bfrom (?:Latin|Old Latin) ([A-Za-z][A-Za-z'\-]*)", re.I), "Classical Latin"),
    (re.compile(r"\bfrom (?:Ancient Greek|Greek) ([A-Za-z][A-Za-z'\-]*)", re.I), "Ancient Greek"),
    (re.compile(r"\bfrom (?:Old English) ([A-Za-z][A-Za-z'\-]*)", re.I), "Old English"),
    (re.compile(r"\bfrom (?:Middle English) ([A-Za-z][A-Za-z'\-]*)", re.I), "Middle English"),
    (re.compile(r"\bfrom (?:Old French|French) ([A-Za-z][A-Za-z'\-]*)", re.I), "Old French"),
]


def _open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def _normalize_word(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def _is_seedable_word(word: str, include_phrases: bool) -> bool:
    if not word or not _SIMPLE_WORD.match(word):
        return False
    return include_phrases or (" " not in word and "-" not in word)


def _iter_json_records(path: Path) -> Iterable[dict[str, Any]]:
    with _open_text(path) as stream:
        if path.name.endswith(".json"):
            payload = json.load(stream)
            if isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        yield item
            elif isinstance(payload, dict):
                records = payload.get("entries") or payload.get("words")
                if isinstance(records, list):
                    for item in records:
                        if isinstance(item, dict):
                            yield item
                else:
                    yield payload
            return

        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                yield item


def _first_gloss(record: dict[str, Any]) -> str:
    for sense in record.get("senses") or []:
        if not isinstance(sense, dict):
            continue
        glosses = sense.get("glosses") or sense.get("raw_glosses") or []
        if glosses:
            return str(glosses[0]).strip()
    return ""


def _etymology_text(record: dict[str, Any]) -> str:
    value = record.get("etymology_text") or record.get("etymology") or ""
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    return str(value).strip()


def _root_from_etymology(text: str, word: str) -> tuple[str, str, str]:
    for pattern, language in _ROOT_PATTERNS:
        match = pattern.search(text)
        if match:
            root = match.group(1).strip("*").casefold()
            return root, text[:500], language
    return word, text[:500] or "Wiktionary lexical entry; etymology pending review", "Modern English"


def _related_terms(record: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for key in ("related", "derived", "descendants", "synonyms"):
        for item in record.get(key) or []:
            if isinstance(item, dict):
                value = item.get("word") or item.get("term")
            else:
                value = item
            term = _normalize_word(value)
            if term and term not in terms and _is_seedable_word(term, include_phrases=False):
                terms.append(term)
            if len(terms) >= 10:
                return terms
    return terms


def load_kaikki_entries(
    path: str | Path,
    limit: int | None = 5000,
    language_code: str = "en",
    include_phrases: bool = True,
) -> list[WordEntry]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Kaikki/Wiktextract file not found: {file_path}")

    entries: list[WordEntry] = []
    seen: set[str] = set()
    for record in _iter_json_records(file_path):
        if record.get("lang_code") and record.get("lang_code") != language_code:
            continue
        word = _normalize_word(record.get("word"))
        if word in seen or not _is_seedable_word(word, include_phrases):
            continue
        definition = _first_gloss(record)
        etymology = _etymology_text(record)
        root_name, root_meaning, root_language = _root_from_etymology(etymology, word)

        seen.add(word)
        entries.append(WordEntry(
            name=word,
            language="English",
            definition=definition or "(Kaikki/Wiktionary lexical entry; definition pending review)",
            root_name=root_name,
            root_meaning=root_meaning,
            root_origin_language=root_language,
            cognates=_related_terms(record),
            etymology_claims=[
                EtymologyClaim(
                    source_form=root_name,
                    source_language=root_language,
                    relation_type="derived_from",
                    source_slug=KAIKKI_SOURCE_SLUG,
                    confidence="medium",
                    note=etymology[:1000] or "Kaikki/Wiktionary etymology field pending review.",
                    is_reconstructed=root_language.startswith("Proto-") or root_name.startswith("*"),
                )
            ] if root_name != word or etymology else None,
            era_meanings=[
                {
                    "era_name": "Modern English",
                    "meaning": definition or etymology or f"Kaikki/Wiktionary entry for '{word}'.",
                    "usage_example": None,
                    "register": "general",
                    "source": KAIKKI_SOURCE_SLUG,
                    "confidence": "medium",
                }
            ],
        ))
        if limit is not None and len(entries) >= limit:
            break
    return entries


def _register_source(ingestor: LexiconIngestor) -> None:
    for source in ALL_SOURCES:
        if source["slug"] == KAIKKI_SOURCE_SLUG:
            ingestor.ingest_source(source)
            return
    raise RuntimeError(f"Source '{KAIKKI_SOURCE_SLUG}' is not in ALL_SOURCES")


def import_from_kaikki(
    path: str | Path,
    limit: int | None = 5000,
    language_code: str = "en",
    include_phrases: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    print(f"[kaikki] Loading {path}...")
    entries = load_kaikki_entries(path, limit=limit, language_code=language_code, include_phrases=include_phrases)
    print(f"[kaikki] Built {len(entries)} WordEntry objects")

    if dry_run:
        for entry in entries[:10]:
            print(f"  {entry.name} | root={entry.root_name} ({entry.root_origin_language}) | def={entry.definition[:70]}")
        print("  [dry_run] — no data written")
        return {"entries": len(entries), "dry_run": True}

    ingestor = LexiconIngestor()
    ingestor.ensure_indexes()
    _register_source(ingestor)
    results = ingestor.bulk_ingest(entries)
    for entry in entries:
        try:
            ingestor.write_attested_in(entry.name, entry.language, KAIKKI_SOURCE_SLUG)
        except Exception:
            pass
    ingestor.close()
    print(f"[kaikki] Done — ingested={results['ingested']}, failed={results['failed']}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Kaikki/Wiktextract JSONL data into the Living Lexicon.")
    parser.add_argument("--path", required=True, help="Path to Kaikki JSON, JSONL, or JSONL.GZ export.")
    parser.add_argument("--limit", type=int, default=5000, help="Max entries. Use 0 for no limit.")
    parser.add_argument("--lang", default="en", help="Wiktextract lang_code to include.")
    parser.add_argument("--single-words-only", action="store_true", help="Skip phrases and hyphenated terms.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and preview without writing to Neo4j.")
    args = parser.parse_args()

    import_from_kaikki(
        path=args.path,
        limit=None if args.limit == 0 else args.limit,
        language_code=args.lang,
        include_phrases=not args.single_words_only,
        dry_run=args.dry_run,
    )
