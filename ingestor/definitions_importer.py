"""
Definitions Importer — produces Words/open_definitions.csv from three
stacked open-license sources, replacing the proprietary Collins dataset.

Sources (merged in priority order):
  1. GCIDE (Webster 1913)             — public domain
  2. Open English WordNet 2024        — CC BY 4.0
  3. Kaikki/Wiktextract (Wiktionary)  — CC-BY-SA  [optional, ~1 GB]

The output CSV has two columns: word, definition.
It is consumed by ingestor.words_merge_importer as source 3 in the master
lexicon merge pipeline.

Usage:
  python3 -m ingestor.definitions_importer
  python3 -m ingestor.definitions_importer --sources gcide,oewn,kaikki
  python3 -m ingestor.definitions_importer --dry-run
  python3 -m ingestor.definitions_importer --no-fetch
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import sys
import urllib.request
import zipfile
from html import unescape
from pathlib import Path
from xml.etree import ElementTree as ET

WORDS_DIR = Path(__file__).parent.parent / "Words"
OUTPUT_FILE = WORDS_DIR / "open_definitions.csv"

# Shared cache paths (also used by the Neo4j importers)
GCIDE_CACHE = WORDS_DIR / "gcide.xml"
GCIDE_FALLBACK_CACHE = WORDS_DIR / "gcide_full.txt"
GCIDE_ZIP_CACHE = WORDS_DIR / "gcide-0.54.zip"
OEWN_XML_CACHE = WORDS_DIR / "english-wordnet-2024.xml"
OEWN_ZIP_CACHE = WORDS_DIR / "english-wordnet-2024.zip"
KAIKKI_CACHE = WORDS_DIR / "kaikki-en.jsonl.gz"
KAIKKI_CACHE_PLAIN = WORDS_DIR / "kaikki-en.jsonl"

GCIDE_ZIP_URL = "https://ftp.gnu.org/gnu/gcide/gcide-0.54.zip"
GCIDE_CHAPTER_URL = "https://gcide.gnu.org.ua/gcide_{n:02d}.txt"
GCIDE_NUM_CHAPTERS = 27
OEWN_ZIP_URL = (
    "https://github.com/globalwordnet/english-wordnet/releases/download/"
    "2024-edition/english-wordnet-2024.zip"
)
KAIKKI_URL = (
    "https://kaikki.org/dictionary/English/"
    "kaikki.org-dictionary-English.jsonl.gz"
)

# Shared word validation regex (identical to the three Neo4j importers)
_WORD_RE = re.compile(r"^[a-z][a-z' -]{1,79}$")

# GCIDE parsing patterns (from gcide_importer.py)
_ENTRY_PATTERN = re.compile(r"<ent>(?P<word>.*?)</ent>(?P<body>.*?)(?=<ent>|$)", re.I | re.S)
_DEF_PATTERN = re.compile(r"<def>(?P<definition>.*?)</def>", re.I | re.S)
_TAG_PATTERN = re.compile(r"<[^>]+>")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _clean_tags(value: str) -> str:
    value = _TAG_PATTERN.sub(" ", value)
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _normalise_key(word: str) -> str:
    return re.sub(r"\s+", " ", word.strip().casefold())


def _is_valid(word: str) -> bool:
    return bool(word) and bool(_WORD_RE.match(word))


def _download(url: str, dest: Path, label: str) -> bool:
    print(f"  Downloading {label} → {dest.name} …")
    try:
        urllib.request.urlretrieve(url, dest)
        print(f"  Download complete ({dest.stat().st_size // 1024:,} KB).")
        return True
    except Exception as exc:
        print(f"  [warn] Download failed: {exc}", file=sys.stderr)
        if dest.exists():
            dest.unlink()
        return False


# ---------------------------------------------------------------------------
# GCIDE  (public domain — Webster 1913)
# ---------------------------------------------------------------------------

def _ensure_gcide(skip_fetch: bool) -> Path | None:
    for candidate in (GCIDE_CACHE, GCIDE_FALLBACK_CACHE, GCIDE_ZIP_CACHE):
        if candidate.exists():
            return candidate

    if skip_fetch:
        print("  [skip] GCIDE file not found and --no-fetch set.", file=sys.stderr)
        return None

    if _download(GCIDE_ZIP_URL, GCIDE_ZIP_CACHE, "GCIDE 0.54 zip"):
        return GCIDE_ZIP_CACHE

    print(f"  GCIDE not cached — downloading {GCIDE_NUM_CHAPTERS} chapter files …")
    chunks: list[str] = []
    for n in range(GCIDE_NUM_CHAPTERS):
        url = GCIDE_CHAPTER_URL.format(n=n)
        tmp = WORDS_DIR / f"gcide_{n:02d}.tmp"
        if _download(url, tmp, f"gcide chapter {n:02d}"):
            chunks.append(tmp.read_text(encoding="utf-8", errors="ignore"))
            tmp.unlink()
        else:
            print(f"  [warn] Skipping chapter {n:02d}; GCIDE output may be incomplete.", file=sys.stderr)

    if not chunks:
        return None

    combined = "\n".join(chunks)
    GCIDE_FALLBACK_CACHE.write_text(combined, encoding="utf-8")
    print(f"  Saved combined GCIDE → {GCIDE_FALLBACK_CACHE.name}")
    return GCIDE_FALLBACK_CACHE


def parse_gcide(path: Path) -> dict[str, str]:
    print(f"  Parsing GCIDE ({path.name}) …")
    if path.suffix == ".zip":
        chunks = []
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if Path(name).name.startswith("CIDE."):
                    chunks.append(zf.read(name).decode("utf-8", errors="ignore"))
        text = "\n".join(chunks)
    else:
        text = path.read_text(encoding="utf-8", errors="ignore")
    defs: dict[str, str] = {}

    for match in _ENTRY_PATTERN.finditer(text):
        word = _normalise_key(_clean_tags(match.group("word")))
        if not _is_valid(word) or word in defs:
            continue
        def_match = _DEF_PATTERN.search(match.group("body"))
        if not def_match:
            continue
        definition = _clean_tags(def_match.group("definition"))[:500]
        if definition:
            defs[word] = definition

    print(f"  GCIDE: {len(defs):,} definitions extracted.")
    return defs


# ---------------------------------------------------------------------------
# Open English WordNet  (CC BY 4.0)
# ---------------------------------------------------------------------------

def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _ensure_oewn(skip_fetch: bool) -> Path | None:
    if OEWN_XML_CACHE.exists():
        return OEWN_XML_CACHE
    if OEWN_ZIP_CACHE.exists():
        return OEWN_ZIP_CACHE

    if skip_fetch:
        print("  [skip] OEWN file not found and --no-fetch set.", file=sys.stderr)
        return None

    if not _download(OEWN_ZIP_URL, OEWN_ZIP_CACHE, "Open English WordNet 2024"):
        return None
    return OEWN_ZIP_CACHE


def _open_oewn(path: Path):
    if path.suffix == ".zip":
        zf = zipfile.ZipFile(path)
        xml_names = [n for n in zf.namelist() if n.endswith(".xml")]
        if not xml_names:
            zf.close()
            raise FileNotFoundError(f"No XML inside {path}")
        return zf.open(xml_names[0]), zf
    fh = path.open("rb")
    return fh, None


def _parse_oewn_data_files(path: Path) -> dict[str, str]:
    """Parse OEWN archives distributed in Princeton WordNet data.* format."""
    if path.suffix != ".zip":
        return {}

    defs: dict[str, str] = {}
    with zipfile.ZipFile(path) as zf:
        data_names = [n for n in zf.namelist() if Path(n).name in {"data.noun", "data.verb", "data.adj", "data.adv"}]
        for name in data_names:
            with zf.open(name) as fh:
                for raw in fh:
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if not line or line.startswith("  "):
                        continue
                    if "|" not in line:
                        continue
                    left, gloss = line.split("|", 1)
                    definition = gloss.split(";", 1)[0].strip()
                    parts = left.split()
                    if len(parts) < 5:
                        continue
                    try:
                        word_count = int(parts[3], 16)
                    except ValueError:
                        continue
                    start = 4
                    for i in range(word_count):
                        idx = start + (i * 2)
                        if idx >= len(parts):
                            break
                        lemma = _normalise_key(parts[idx].replace("_", " "))
                        if lemma and definition and _is_valid(lemma) and lemma not in defs:
                            defs[lemma] = definition[:500]
    return defs


def _load_oewn_synsets(path: Path) -> dict[str, str]:
    stream, zf = _open_oewn(path)
    synsets: dict[str, str] = {}
    try:
        for _, el in ET.iterparse(stream, events=("end",)):
            if _tag(el) != "Synset":
                el.clear()
                continue
            synset_id = el.attrib.get("id", "")
            definition = ""
            for child in el:
                if _tag(child) == "Definition" and child.text:
                    definition = child.text.strip()
                    break
            if synset_id and definition:
                synsets[synset_id] = definition
            el.clear()
    finally:
        stream.close()
        if zf:
            zf.close()
    return synsets


def parse_oewn(path: Path) -> dict[str, str]:
    print(f"  Parsing OEWN ({path.name}) …")
    data_defs = _parse_oewn_data_files(path)
    if data_defs:
        print(f"  OEWN: {len(data_defs):,} definitions extracted.")
        return data_defs

    synsets = _load_oewn_synsets(path)

    stream, zf = _open_oewn(path)
    defs: dict[str, str] = {}
    try:
        for _, el in ET.iterparse(stream, events=("end",)):
            if _tag(el) != "LexicalEntry":
                el.clear()
                continue
            lemma = ""
            first_synset = ""
            for child in el:
                child_tag = _tag(child)
                if child_tag == "Lemma":
                    raw = child.attrib.get("writtenForm", "").replace("_", " ")
                    lemma = _normalise_key(raw)
                elif child_tag == "Sense" and not first_synset:
                    first_synset = child.attrib.get("synset", "")
            if lemma and _is_valid(lemma) and lemma not in defs:
                definition = synsets.get(first_synset, "")
                if definition:
                    defs[lemma] = definition[:500]
            el.clear()
    finally:
        stream.close()
        if zf:
            zf.close()

    print(f"  OEWN: {len(defs):,} definitions extracted.")
    return defs


# ---------------------------------------------------------------------------
# Kaikki / Wiktextract  (CC-BY-SA — optional)
# ---------------------------------------------------------------------------

def _ensure_kaikki(skip_fetch: bool) -> Path | None:
    for candidate in (KAIKKI_CACHE, KAIKKI_CACHE_PLAIN):
        if candidate.exists():
            return candidate

    if skip_fetch:
        print("  [skip] Kaikki file not found and --no-fetch set.", file=sys.stderr)
        return None

    print("  NOTE: Kaikki download is ~1 GB. This will take several minutes.")
    if not _download(KAIKKI_URL, KAIKKI_CACHE, "Kaikki/Wiktextract English"):
        return None
    return KAIKKI_CACHE


def parse_kaikki(path: Path) -> dict[str, str]:
    print(f"  Parsing Kaikki ({path.name}) …")
    defs: dict[str, str] = {}
    open_fn = gzip.open if path.suffix == ".gz" else path.open
    with open_fn(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            lang_code = record.get("lang_code", "")
            if lang_code and lang_code != "en":
                continue
            word = _normalise_key(str(record.get("word", "")))
            if not _is_valid(word) or word in defs:
                continue
            gloss = ""
            for sense in record.get("senses") or []:
                if not isinstance(sense, dict):
                    continue
                glosses = sense.get("glosses") or sense.get("raw_glosses") or []
                if glosses:
                    gloss = str(glosses[0]).strip()
                    break
            if gloss:
                defs[word] = gloss[:500]

    print(f"  Kaikki: {len(defs):,} definitions extracted.")
    return defs


# ---------------------------------------------------------------------------
# Merge + write
# ---------------------------------------------------------------------------

SOURCE_META = {
    "gcide": {
        "definition_source_slug": "gcide",
        "definition_source_name": "GCIDE / Webster 1913",
        "definition_license": "public-domain",
    },
    "oewn": {
        "definition_source_slug": "oewn-2024",
        "definition_source_name": "Open English WordNet 2024",
        "definition_license": "CC-BY-4.0",
    },
    "kaikki": {
        "definition_source_slug": "kaikki-en",
        "definition_source_name": "Kaikki/Wiktextract English",
        "definition_license": "CC-BY-SA",
    },
}


def merge_definitions(*sources: tuple[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for source_slug, source in sources:
        meta = SOURCE_META[source_slug]
        for word, definition in source.items():
            if word not in merged:
                merged[word] = {
                    "word": word,
                    "definition": definition,
                    **meta,
                }
    return merged


def write_output(defs: dict[str, dict[str, str]], output: Path, dry_run: bool) -> None:
    sorted_items = sorted(defs.values(), key=lambda row: row["word"])

    if dry_run:
        print(f"\n[dry_run] Would write {len(sorted_items):,} definitions → {output}")
        print("  Sample (first 15):")
        for row in sorted_items[:15]:
            preview = row["definition"][:70] + "…" if len(row["definition"]) > 70 else row["definition"]
            print(f"    {row['word']:<25s}  {row['definition_source_slug']:<10s}  {preview}")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "word",
                "definition",
                "definition_source_slug",
                "definition_source_name",
                "definition_license",
            ],
        )
        writer.writeheader()
        writer.writerows(sorted_items)

    print(f"\n[done] Wrote {len(sorted_items):,} definitions → {output}")


# ---------------------------------------------------------------------------
# Public loader  (used by words_merge_importer)
# ---------------------------------------------------------------------------

def load_open_definitions(path: Path) -> dict[str, str]:
    """Load Words/open_definitions.csv — returns word (normalised) → definition."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            word = _normalise_key(row.get("word", ""))
            definition = (row.get("definition") or "").strip()
            if word and definition:
                result[word] = definition
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Words/open_definitions.csv from open-license sources."
    )
    parser.add_argument(
        "--sources",
        default="gcide,oewn",
        help="Comma-separated list of sources to include: gcide, oewn, kaikki. "
             "Default: gcide,oewn (Kaikki omitted by default due to ~1 GB download).",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Only use locally cached files; skip network downloads.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and preview without writing output.",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_FILE),
        help="Output CSV path (default: Words/open_definitions.csv).",
    )
    args = parser.parse_args()

    sources = [s.strip().lower() for s in args.sources.split(",") if s.strip()]
    output = Path(args.output)

    print("=== Living Lexicon — Open Definitions Builder ===\n")
    print(f"Sources: {', '.join(sources)}")
    print(f"Fetch:   {'disabled' if args.no_fetch else 'enabled'}\n")

    stacked: list[tuple[str, dict[str, str]]] = []

    if "gcide" in sources:
        print("[GCIDE — Webster 1913, public domain]")
        gcide_path = _ensure_gcide(skip_fetch=args.no_fetch)
        if gcide_path:
            stacked.append(("gcide", parse_gcide(gcide_path)))
        print()

    if "oewn" in sources:
        print("[Open English WordNet 2024 — CC BY 4.0]")
        oewn_path = _ensure_oewn(skip_fetch=args.no_fetch)
        if oewn_path:
            stacked.append(("oewn", parse_oewn(oewn_path)))
        print()

    if "kaikki" in sources:
        print("[Kaikki/Wiktextract — CC-BY-SA]")
        kaikki_path = _ensure_kaikki(skip_fetch=args.no_fetch)
        if kaikki_path:
            stacked.append(("kaikki", parse_kaikki(kaikki_path)))
        print()

    if not stacked:
        print("[error] No definitions loaded — all sources failed or skipped.", file=sys.stderr)
        sys.exit(1)

    merged = merge_definitions(*stacked)
    print(f"Total unique definitions: {len(merged):,}")

    write_output(merged, output, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
