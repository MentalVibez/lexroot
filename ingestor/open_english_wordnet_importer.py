"""
Open English WordNet importer.

Consumes the Open English WordNet XML release, either directly as XML or inside
the official ZIP. This is a cleaner modern lexical coverage layer than the older
bundled WordNet plugin data, with stable synset definitions and CC BY 4.0 terms.

Usage:
  python -m ingestor.open_english_wordnet_importer --path Words/english-wordnet-2024.xml --limit 1000 --dry-run
  python -m ingestor.open_english_wordnet_importer --path Words/english-wordnet-2024.zip --limit 0
"""
from __future__ import annotations

import argparse
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, BinaryIO
from xml.etree import ElementTree as ET

from ingestor.graph_loader import LexiconIngestor, WordEntry
from ingestor.sources_catalog import ALL_SOURCES


OEWN_SOURCE_SLUG = "open-english-wordnet"
_WORD = re.compile(r"^[a-z][a-z' -]{1,79}$")


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _normalize(value: str) -> str:
    value = str(value or "").replace("_", " ").strip().casefold()
    return re.sub(r"\s+", " ", value)


def _is_seedable(word: str, include_phrases: bool = True) -> bool:
    if not word or not _WORD.match(word):
        return False
    if not include_phrases and (" " in word or "-" in word):
        return False
    return True


class _ZipXml:
    def __init__(self, path: Path):
        self.path = path
        self.zip_file: zipfile.ZipFile | None = None
        self.stream: BinaryIO | None = None

    def __enter__(self) -> BinaryIO:
        self.zip_file = zipfile.ZipFile(self.path)
        xml_names = [name for name in self.zip_file.namelist() if name.endswith(".xml")]
        if not xml_names:
            raise FileNotFoundError(f"No XML file found inside {self.path}")
        self.stream = self.zip_file.open(xml_names[0])
        return self.stream

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.stream:
            self.stream.close()
        if self.zip_file:
            self.zip_file.close()


def _open_xml(path: Path):
    if path.suffix == ".zip":
        return _ZipXml(path)
    return path.open("rb")


def _load_synset_definitions(path: Path) -> dict[str, str]:
    definitions: dict[str, str] = {}
    with _open_xml(path) as stream:
        for _, element in ET.iterparse(stream, events=("end",)):
            if _tag(element) != "Synset":
                continue
            synset_id = element.attrib.get("id", "")
            definition = ""
            for child in element:
                if _tag(child) == "Definition" and child.text:
                    definition = child.text.strip()
                    break
            if synset_id and definition:
                definitions[synset_id] = definition
            element.clear()
    return definitions


def load_open_english_wordnet_entries(
    path: str | Path,
    limit: int | None = 5000,
    include_phrases: bool = True,
) -> list[WordEntry]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Open English WordNet file not found: {file_path}")

    definitions = _load_synset_definitions(file_path)
    groups: dict[str, dict[str, Any]] = {}

    with _open_xml(file_path) as stream:
        for _, element in ET.iterparse(stream, events=("end",)):
            if _tag(element) != "LexicalEntry":
                continue

            lemma = ""
            sense_ids: list[str] = []
            for child in element:
                child_tag = _tag(child)
                if child_tag == "Lemma":
                    lemma = _normalize(child.attrib.get("writtenForm", ""))
                elif child_tag == "Sense":
                    synset_id = child.attrib.get("synset")
                    if synset_id:
                        sense_ids.append(synset_id)

            if lemma and _is_seedable(lemma, include_phrases=include_phrases):
                group = groups.setdefault(lemma, {"definitions": [], "synsets": set()})
                for synset_id in sense_ids:
                    group["synsets"].add(synset_id)
                    definition = definitions.get(synset_id)
                    if definition and definition not in group["definitions"]:
                        group["definitions"].append(definition)

            element.clear()
            if limit is not None and len(groups) >= limit:
                break

    entries: list[WordEntry] = []
    for word, group in groups.items():
        definition = group["definitions"][0] if group["definitions"] else "(Open English WordNet lexical entry; definition pending review)"
        synsets = sorted(group["synsets"])
        entries.append(WordEntry(
            name=word,
            language="English",
            definition=definition,
            root_name=word,
            root_meaning="Open English WordNet lexical entry; etymology pending enrichment",
            root_origin_language="Modern English",
            cognates=None,
            era_meanings=[
                {
                    "era_name": "Modern English",
                    "meaning": definition,
                    "usage_example": None,
                    "register": "general",
                    "source": OEWN_SOURCE_SLUG,
                    "confidence": "medium",
                }
            ],
        ))
        # Preserve synset IDs as a compact citation context through ATTESTED_IN later.
        entries[-1]._oewn_context = ",".join(synsets[:5])  # type: ignore[attr-defined]
    return entries


def _register_source(ingestor: LexiconIngestor) -> None:
    for source in ALL_SOURCES:
        if source["slug"] == OEWN_SOURCE_SLUG:
            ingestor.ingest_source(source)
            return
    raise RuntimeError(f"Source '{OEWN_SOURCE_SLUG}' is not in ALL_SOURCES")


def import_from_open_english_wordnet(
    path: str | Path,
    limit: int | None = 5000,
    include_phrases: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    print(f"[oewn] Loading {path}...")
    entries = load_open_english_wordnet_entries(path, limit=limit, include_phrases=include_phrases)
    print(f"[oewn] Built {len(entries)} WordEntry objects")

    if dry_run:
        for entry in entries[:10]:
            print(f"  {entry.name} | def={entry.definition[:70]}")
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
                OEWN_SOURCE_SLUG,
                getattr(entry, "_oewn_context", ""),
            )
        except Exception:
            pass
    ingestor.close()
    print(f"[oewn] Done — ingested={results['ingested']}, failed={results['failed']}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Open English WordNet XML/ZIP data into the Living Lexicon.")
    parser.add_argument("--path", required=True, help="Path to Open English WordNet XML or ZIP.")
    parser.add_argument("--limit", type=int, default=5000, help="Max entries. Use 0 for no limit.")
    parser.add_argument("--single-words-only", action="store_true", help="Skip phrases and hyphenated terms.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and preview without writing to Neo4j.")
    args = parser.parse_args()

    import_from_open_english_wordnet(
        path=args.path,
        limit=None if args.limit == 0 else args.limit,
        include_phrases=not args.single_words_only,
        dry_run=args.dry_run,
    )
