"""
Wikidata Lexeme importer.

Consumes local Wikidata lexeme JSON/JSONL exports. This layer is best for CC0
external identifiers, lemmas, forms, and short sense glosses. It should not be
treated as an etymology authority by itself.

Usage:
  python -m ingestor.wikidata_lexeme_importer --path Words/wikidata-lexemes-en.jsonl.gz --limit 1000 --dry-run
  python -m ingestor.wikidata_lexeme_importer --path Words/wikidata-lexemes.json --limit 0
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
from pathlib import Path
from typing import Any, Iterable

from ingestor.graph_loader import LexiconIngestor, WordEntry
from ingestor.sources_catalog import ALL_SOURCES


WIKIDATA_LEXEMES_SOURCE_SLUG = "wikidata-lexemes"
_WORD = re.compile(r"^[a-z][a-z' -]{1,79}$")


def _open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def _normalize(value: Any) -> str:
    value = str(value or "").strip().replace("_", " ").casefold()
    return re.sub(r"\s+", " ", value)


def _is_seedable(word: str, include_phrases: bool = True) -> bool:
    if not word or not _WORD.match(word):
        return False
    if not include_phrases and (" " in word or "-" in word):
        return False
    return True


def _iter_records(path: Path) -> Iterable[dict[str, Any]]:
    with _open_text(path) as stream:
        if path.name.endswith(".json"):
            payload = json.load(stream)
            if isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        yield item
            elif isinstance(payload, dict):
                entities = payload.get("entities")
                if isinstance(entities, dict):
                    for item in entities.values():
                        if isinstance(item, dict):
                            yield item
                else:
                    yield payload
            return

        for line in stream:
            line = line.strip().rstrip(",")
            if not line or line in {"[", "]"}:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                yield item


def _lemma(record: dict[str, Any], language: str) -> str:
    lemmas = record.get("lemmas") or {}
    if isinstance(lemmas, dict):
        preferred = lemmas.get(language) or lemmas.get("en")
        if isinstance(preferred, dict):
            return _normalize(preferred.get("value"))
        for value in lemmas.values():
            if isinstance(value, dict):
                return _normalize(value.get("value"))
    return ""


def _language(record: dict[str, Any]) -> str:
    value = record.get("language")
    if isinstance(value, str):
        return value.rsplit("/", 1)[-1]
    return ""


def _sense_gloss(record: dict[str, Any], language: str) -> str:
    for sense in record.get("senses") or []:
        if not isinstance(sense, dict):
            continue
        glosses = sense.get("glosses") or {}
        if isinstance(glosses, dict):
            preferred = glosses.get(language) or glosses.get("en")
            if isinstance(preferred, dict) and preferred.get("value"):
                return str(preferred["value"]).strip()
    return ""


def _forms(record: dict[str, Any], language: str) -> list[str]:
    forms: list[str] = []
    for form in record.get("forms") or []:
        if not isinstance(form, dict):
            continue
        reps = form.get("representations") or {}
        preferred = reps.get(language) or reps.get("en") if isinstance(reps, dict) else None
        if isinstance(preferred, dict):
            value = _normalize(preferred.get("value"))
            if value and value not in forms and _is_seedable(value, include_phrases=False):
                forms.append(value)
        if len(forms) >= 10:
            break
    return forms


def load_wikidata_lexeme_entries(
    path: str | Path,
    limit: int | None = 5000,
    language_code: str = "en",
    include_phrases: bool = True,
) -> list[WordEntry]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Wikidata lexeme file not found: {file_path}")

    entries: list[WordEntry] = []
    seen: set[str] = set()
    for record in _iter_records(file_path):
        # Wikidata dump language values are entity IRIs/IDs rather than ISO codes.
        # For downloaded English-only extracts, the lemma language is the reliable filter.
        word = _lemma(record, language_code)
        if word in seen or not _is_seedable(word, include_phrases=include_phrases):
            continue

        lexeme_id = str(record.get("id") or "").strip()
        gloss = _sense_gloss(record, language_code)
        seen.add(word)
        entries.append(WordEntry(
            name=word,
            language="English",
            definition=gloss or f"(Wikidata Lexeme {lexeme_id}; definition pending enrichment)",
            root_name=word,
            root_meaning=f"Wikidata Lexeme {lexeme_id}; etymology pending enrichment",
            root_origin_language="Modern English",
            cognates=_forms(record, language_code),
            era_meanings=[
                {
                    "era_name": "Modern English",
                    "meaning": gloss or f"Wikidata lexeme record for '{word}'.",
                    "usage_example": None,
                    "register": "general",
                    "source": WIKIDATA_LEXEMES_SOURCE_SLUG,
                    "confidence": "medium",
                }
            ],
        ))
        entries[-1]._wikidata_context = lexeme_id  # type: ignore[attr-defined]
        if limit is not None and len(entries) >= limit:
            break
    return entries


def _register_source(ingestor: LexiconIngestor) -> None:
    for source in ALL_SOURCES:
        if source["slug"] == WIKIDATA_LEXEMES_SOURCE_SLUG:
            ingestor.ingest_source(source)
            return
    raise RuntimeError(f"Source '{WIKIDATA_LEXEMES_SOURCE_SLUG}' is not in ALL_SOURCES")


def import_from_wikidata_lexemes(
    path: str | Path,
    limit: int | None = 5000,
    language_code: str = "en",
    include_phrases: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    print(f"[wikidata-lexemes] Loading {path}...")
    entries = load_wikidata_lexeme_entries(
        path,
        limit=limit,
        language_code=language_code,
        include_phrases=include_phrases,
    )
    print(f"[wikidata-lexemes] Built {len(entries)} WordEntry objects")

    if dry_run:
        for entry in entries[:10]:
            print(f"  {entry.name} | context={getattr(entry, '_wikidata_context', '')} | def={entry.definition[:70]}")
        print("  [dry_run] — no data written")
        return {"entries": len(entries), "dry_run": True}

    ingestor = LexiconIngestor()
    ingestor.ensure_indexes()
    _register_source(ingestor)
    results = ingestor.bulk_ingest(entries)
    for entry in entries:
        try:
            ingestor.write_attested_in(
                entry.name,
                entry.language,
                WIKIDATA_LEXEMES_SOURCE_SLUG,
                getattr(entry, "_wikidata_context", ""),
            )
        except Exception:
            pass
    ingestor.close()
    print(f"[wikidata-lexemes] Done — ingested={results['ingested']}, failed={results['failed']}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Wikidata Lexeme JSON/JSONL data into the Living Lexicon.")
    parser.add_argument("--path", required=True, help="Path to Wikidata Lexeme JSON, JSONL, or JSONL.GZ.")
    parser.add_argument("--limit", type=int, default=5000, help="Max entries. Use 0 for no limit.")
    parser.add_argument("--lang", default="en", help="Lemma/gloss language code to include.")
    parser.add_argument("--single-words-only", action="store_true", help="Skip phrases and hyphenated terms.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and preview without writing to Neo4j.")
    args = parser.parse_args()

    import_from_wikidata_lexemes(
        path=args.path,
        limit=None if args.limit == 0 else args.limit,
        language_code=args.lang,
        include_phrases=not args.single_words_only,
        dry_run=args.dry_run,
    )
