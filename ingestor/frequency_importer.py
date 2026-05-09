"""
Frequency metadata importer.

Consumes local CSV/TSV/JSON/JSONL frequency exports such as SUBTLEX-US or a
wordfreq-derived table. It annotates Word nodes with frequency/rank metadata
instead of replacing definitions or etymology.

Expected flexible columns:
  word, term, lemma
  count, frequency, freq, value
  rank
  zipf, zipf_frequency

Usage:
  python -m ingestor.frequency_importer --path Words/subtlex-us.tsv --source subtlex-us --dry-run
  python -m ingestor.frequency_importer --path Words/wordfreq.csv --source wordfreq --limit 0
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
from pathlib import Path
from typing import Any, Iterable

from ingestor.graph_loader import LexiconIngestor
from ingestor.sources_catalog import ALL_SOURCES


WORD_KEYS = ["word", "term", "lemma", "headword", "entry"]
COUNT_KEYS = ["count", "frequency", "freq", "value", "subtlexwf", "word_frequency"]
RANK_KEYS = ["rank", "frequency_rank", "freq_rank"]
ZIPF_KEYS = ["zipf", "zipf_frequency", "zipf_freq"]
_WORD = re.compile(r"^[a-z][a-z' -]{1,79}$")


def _open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def _normalize_word(value: Any) -> str:
    value = str(value or "").strip().replace("_", " ").casefold()
    return re.sub(r"\s+", " ", value)


def _is_word(value: str, include_phrases: bool = True) -> bool:
    if not value or not _WORD.match(value):
        return False
    return include_phrases or (" " not in value and "-" not in value)


def _get(row: dict[str, Any], keys: list[str]) -> Any:
    normalized = {str(k).strip().lower(): v for k, v in row.items()}
    for key in keys:
        value = normalized.get(key)
        if value not in (None, ""):
            return value
    return None


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def _int(value: Any) -> int | None:
    number = _float(value)
    return int(number) if number is not None else None


def _iter_rows(path: Path) -> Iterable[dict[str, Any]]:
    with _open_text(path) as stream:
        if path.name.endswith(".json"):
            payload = json.load(stream)
            if isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        yield item
            elif isinstance(payload, dict):
                records = payload.get("entries") or payload.get("words") or payload.get("data")
                if isinstance(records, list):
                    for item in records:
                        if isinstance(item, dict):
                            yield item
                else:
                    yield payload
            return

        if path.suffix in {".jsonl", ".gz"} and ".jsonl" in path.name:
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
            return

        delimiter = "\t" if path.suffix == ".tsv" or ".tsv" in path.name else ","
        reader = csv.DictReader(stream, delimiter=delimiter)
        for row in reader:
            yield dict(row)


def load_frequency_records(
    path: str | Path,
    limit: int | None = 5000,
    include_phrases: bool = True,
) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Frequency file not found: {file_path}")

    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    auto_rank = 0
    for row in _iter_rows(file_path):
        word = _normalize_word(_get(row, WORD_KEYS))
        if word in seen or not _is_word(word, include_phrases=include_phrases):
            continue
        auto_rank += 1
        seen.add(word)
        records.append({
            "word": word,
            "frequency": _float(_get(row, COUNT_KEYS)),
            "rank": _int(_get(row, RANK_KEYS)) or auto_rank,
            "zipf": _float(_get(row, ZIPF_KEYS)),
        })
        if limit is not None and len(records) >= limit:
            break
    return records


def _register_source(ingestor: LexiconIngestor, source_slug: str) -> None:
    for source in ALL_SOURCES:
        if source["slug"] == source_slug:
            ingestor.ingest_source(source)
            return
    raise RuntimeError(f"Source '{source_slug}' is not in ALL_SOURCES")


def import_frequency_metadata(
    path: str | Path,
    source_slug: str,
    limit: int | None = 5000,
    include_phrases: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    print(f"[frequency] Loading {path} as {source_slug}...")
    records = load_frequency_records(path, limit=limit, include_phrases=include_phrases)
    print(f"[frequency] Parsed {len(records)} frequency records")

    if dry_run:
        for record in records[:10]:
            print(
                f"  {record['word']} | rank={record['rank']}"
                f" | freq={record['frequency']} | zipf={record['zipf']}"
            )
        print("  [dry_run] — no data written")
        return {"records": len(records), "dry_run": True}

    ingestor = LexiconIngestor()
    ingestor.ensure_indexes()
    _register_source(ingestor, source_slug)
    failed = 0
    for record in records:
        try:
            ingestor.annotate_frequency(
                record["word"],
                "English",
                source_slug,
                frequency=record["frequency"],
                rank=record["rank"],
                zipf=record["zipf"],
            )
        except Exception:
            failed += 1
    ingestor.close()
    print(f"[frequency] Done — annotated={len(records) - failed}, failed={failed}")
    return {"annotated": len(records) - failed, "failed": failed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import word frequency metadata into the Living Lexicon.")
    parser.add_argument("--path", required=True, help="Path to CSV/TSV/JSON/JSONL frequency file.")
    parser.add_argument("--source", required=True, choices=["wordfreq", "subtlex-us"], help="Frequency source slug.")
    parser.add_argument("--limit", type=int, default=5000, help="Max records. Use 0 for no limit.")
    parser.add_argument("--single-words-only", action="store_true", help="Skip phrases and hyphenated terms.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and preview without writing to Neo4j.")
    args = parser.parse_args()

    import_frequency_metadata(
        path=args.path,
        source_slug=args.source,
        limit=None if args.limit == 0 else args.limit,
        include_phrases=not args.single_words_only,
        dry_run=args.dry_run,
    )
