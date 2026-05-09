"""
DotishPhilosopher Importer — bulk-loads DotishPhilosopher lexicon data into Neo4j.

Supported input formats:
  - JSON: list of entries or {"entries": [...]}
  - CSV/TSV: rows with named columns such as word, definition, root_word,
    root_meaning, root_origin_language, attested_year, cognates,
    era_name, meaning, usage_example, register, confidence, source.

The importer is intentionally flexible so DotishPhilosopher exports can be mapped
into the repository's existing `WordEntry` / Neo4j ingestion model.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from ingestor.graph_loader import LexiconIngestor, WordEntry

DOTISH_PHILOSOPHER_SOURCE = {
    "slug": "dotish-philosopher",
    "short_name": "DotishPhilosopher",
    "full_name": "DotishPhilosopher Lexicon",
    "author": "DotishPhilosopher",
    "year": 2026,
    "publisher": "DotishPhilosopher",
    "category": "online-lexicon",
    "authority_tier": 3,
    "description": "Imported lexicon data from DotishPhilosopher.",
}

NAME_KEYS = ["word", "headword", "lemma", "entry", "term"]
DEFINITION_KEYS = ["definition", "def", "gloss", "word_definition"]
ROOT_NAME_KEYS = ["root_name", "root", "root_word", "etymology", "etymological_root"]
ROOT_MEANING_KEYS = ["root_meaning", "root_definition", "root_gloss", "etymology_definition"]
ROOT_ORIGIN_KEYS = ["root_origin_language", "root_language", "origin_language", "etymology_language"]
LANGUAGE_KEYS = ["language", "lang", "word_language"]
ATTESTED_YEAR_KEYS = ["attested_year", "year", "first_attested", "date"]
COGNATES_KEYS = ["cognates", "cognate", "related_words", "related"]
ERA_NAME_KEYS = ["era_name", "era", "period", "historical_period"]
MEANING_KEYS = ["meaning", "era_meaning", "definition", "gloss"]
USAGE_EXAMPLE_KEYS = ["usage_example", "example", "quote", "citation"]
REGISTER_KEYS = ["register", "style", "registers"]
SOURCE_KEYS = ["source", "source_slug", "attested_in", "attestation_source"]
CONFIDENCE_KEYS = ["confidence", "trust", "certainty"]
ERA_MEANINGS_KEYS = ["era_meanings", "meanings", "entries"]


def _normalize_record(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return {str(k).strip().lower(): v for k, v in raw.items()}
    return None


def _get_value(record: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    try:
        return int(float(text))
    except ValueError:
        return None


def _parse_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    separators = [";", ",", "|"]
    for sep in separators:
        if sep in text:
            return [item.strip() for item in text.split(sep) if item.strip()]
    return [text]


def _parse_era_meanings(raw: dict[str, Any], default_source: str) -> list[dict[str, Any]]:
    era_meanings = []
    nested = _get_value(raw, ERA_MEANINGS_KEYS)
    if isinstance(nested, list):
        for item in nested:
            item_record = _normalize_record(item)
            if not item_record:
                continue
            era_name = _get_value(item_record, ERA_NAME_KEYS)
            meaning = _get_value(item_record, MEANING_KEYS)
            if era_name or meaning:
                era_meanings.append({
                    "era_name": era_name or "Modern English",
                    "meaning": meaning or "",
                    "usage_example": _get_value(item_record, USAGE_EXAMPLE_KEYS),
                    "register": _get_value(item_record, REGISTER_KEYS) or "general",
                    "source": _get_value(item_record, SOURCE_KEYS) or default_source,
                    "confidence": _get_value(item_record, CONFIDENCE_KEYS) or "medium",
                })
        return era_meanings

    era_name = _get_value(raw, ERA_NAME_KEYS)
    meaning = _get_value(raw, MEANING_KEYS)
    if era_name or meaning:
        era_meanings.append({
            "era_name": era_name or "Modern English",
            "meaning": meaning or "",
            "usage_example": _get_value(raw, USAGE_EXAMPLE_KEYS),
            "register": _get_value(raw, REGISTER_KEYS) or "general",
            "source": _get_value(raw, SOURCE_KEYS) or default_source,
            "confidence": _get_value(raw, CONFIDENCE_KEYS) or "medium",
        })
    return era_meanings


def _load_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)

    if isinstance(payload, dict):
        if "entries" in payload and isinstance(payload["entries"], list):
            data = payload["entries"]
        elif "words" in payload and isinstance(payload["words"], list):
            data = payload["words"]
        else:
            data = [payload]
    elif isinstance(payload, list):
        data = payload
    else:
        raise ValueError("JSON file must contain a list or a top-level dictionary.")

    return [raw for raw in data if isinstance(raw, dict)]


def _load_csv(path: Path) -> list[dict[str, Any]]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=delimiter)
        return [dict(row) for row in reader]


def load_dotish_records(path: str) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"DotishPhilosopher file not found: {path}")

    if file_path.suffix.lower() in {".json"}:
        return _load_json(file_path)
    if file_path.suffix.lower() in {".csv", ".tsv"}:
        return _load_csv(file_path)

    try:
        return _load_json(file_path)
    except ValueError:
        return _load_csv(file_path)


def build_dotish_word_entries(records: list[dict[str, Any]], source_slug: str = DOTISH_PHILOSOPHER_SOURCE["slug"]) -> list[WordEntry]:
    groups: dict[str, dict[str, Any]] = {}
    for raw in records:
        record = _normalize_record(raw)
        if not record:
            continue

        name = _get_value(record, NAME_KEYS)
        if not name:
            continue
        name = str(name).strip()
        if not name:
            continue

        group = groups.setdefault(name, {
            "name": name,
            "language": _get_value(record, LANGUAGE_KEYS) or "English",
            "definition": _get_value(record, DEFINITION_KEYS) or "",
            "root_name": _get_value(record, ROOT_NAME_KEYS) or name,
            "root_meaning": _get_value(record, ROOT_MEANING_KEYS) or "",
            "root_origin_language": _get_value(record, ROOT_ORIGIN_KEYS) or "Modern English",
            "attested_year": _parse_int(_get_value(record, ATTESTED_YEAR_KEYS)),
            "cognates": set(_parse_list(_get_value(record, COGNATES_KEYS))),
            "era_meanings": [],
        })

        if not group["definition"]:
            group["definition"] = _get_value(record, DEFINITION_KEYS) or group["definition"]

        if not group["root_name"] or group["root_name"] == name:
            group["root_name"] = _get_value(record, ROOT_NAME_KEYS) or group["root_name"]

        if not group["root_origin_language"] or group["root_origin_language"] == "Modern English":
            group["root_origin_language"] = _get_value(record, ROOT_ORIGIN_KEYS) or group["root_origin_language"]

        if group["attested_year"] is None:
            group["attested_year"] = _parse_int(_get_value(record, ATTESTED_YEAR_KEYS))

        cognates = _parse_list(_get_value(record, COGNATES_KEYS))
        group["cognates"].update(cognates)

        era_meanings = _parse_era_meanings(record, source_slug)
        group["era_meanings"].extend(era_meanings)

    entries: list[WordEntry] = []
    for group in groups.values():
        if not group["definition"]:
            group["definition"] = f"(Imported from {source_slug}; definition unavailable)"

        entries.append(WordEntry(
            name=group["name"],
            language=group["language"],
            definition=group["definition"],
            root_name=group["root_name"],
            root_meaning=group["root_meaning"],
            root_origin_language=group["root_origin_language"],
            attested_year=group["attested_year"],
            cognates=sorted(group["cognates"]),
            era_meanings=group["era_meanings"] or None,
        ))
    return entries


def import_from_dotish(
    path: str,
    source_slug: str = DOTISH_PHILOSOPHER_SOURCE["slug"],
    register_source: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    print(f"[dotish] Loading DotishPhilosopher data from {path}…")
    records = load_dotish_records(path)
    print(f"[dotish] Parsed {len(records)} raw records")

    entries = build_dotish_word_entries(records, source_slug=source_slug)
    print(f"[dotish] Built {len(entries)} WordEntry objects")

    if dry_run:
        for entry in entries[:10]:
            print(
                f"  {entry.name} | root={entry.root_name} ({entry.root_origin_language})"
                f" | def={entry.definition[:60]}"
                f" | cognates={entry.cognates[:5]}"
                f" | eras={len(entry.era_meanings or [])}"
            )
        print("  [dry_run] — no data written")
        return {"entries": len(entries), "dry_run": True}

    ingestor = LexiconIngestor()
    ingestor.ensure_indexes()
    if register_source:
        print(f"[dotish] Registering source {source_slug}")
        ingestor.ingest_source(DOTISH_PHILOSOPHER_SOURCE)

    results = ingestor.bulk_ingest(entries)
    ingestor.close()

    print(f"[dotish] Done — ingested={results['ingested']}, failed={results['failed']}")
    if results["errors"]:
        for err in results["errors"][:5]:
            print(f"  ERROR: {err['word']}: {err['error']}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import DotishPhilosopher lexicon exports into the Living Lexicon."
    )
    parser.add_argument(
        "--path",
        required=True,
        help="Path to a DotishPhilosopher JSON, CSV, or TSV export file.",
    )
    parser.add_argument(
        "--source-slug",
        default=DOTISH_PHILOSOPHER_SOURCE["slug"],
        help="Source slug to use for imported entries.",
    )
    parser.add_argument(
        "--no-register-source",
        action="store_true",
        help="Do not register the DotishPhilosopher source node before ingesting.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and preview entries without writing to Neo4j.",
    )
    args = parser.parse_args()

    import_from_dotish(
        path=args.path,
        source_slug=args.source_slug,
        register_source=not args.no_register_source,
        dry_run=args.dry_run,
    )
