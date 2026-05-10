"""
GCIDE Importer — parses the GNU Collaborative International Dictionary of English
(gcide-0.54.zip) and loads words + senses into PostgreSQL.

The zip contains CIDE.A through CIDE.Z — streams of <p>...</p> entry blocks in
a custom SGML-like format based on Webster's 1913 Revised Unabridged Dictionary.

Usage:
    python -m ingestor.gcide_importer
    python -m ingestor.gcide_importer --dry-run
    python -m ingestor.gcide_importer --limit 500
    python -m ingestor.gcide_importer --path Words/gcide-0.54.zip
"""
from __future__ import annotations

import os
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

from ingestor.base import BaseImporter, ImportResult
from ingestor.utils import is_valid_word

SYNC_URL: str = os.getenv(
    "POSTGRES_SYNC_URL",
    "postgresql://lexicon:lexicon_secret@localhost:5432/living_lexicon",
)

SOURCE_SLUG = "1913-webster"
ERA_NAME = "Late Modern English"
FIRST_YEAR = 1890
LAST_YEAR = 1913
EVIDENCE_GRADE = "B"
CONFIDENCE = "medium"
CONFIDENCE_REASON = "Webster's 1913 Revised Unabridged Dictionary via GCIDE."


# ---------------------------------------------------------------------------
# GCIDE markup stripping
# ---------------------------------------------------------------------------

_ENTITY_MAP: dict[str, str] = {
    "eacute": "é", "Eacute": "É", "aacute": "á", "Aacute": "Á",
    "iacute": "í", "Iacute": "Í", "oacute": "ó", "Oacute": "Ó",
    "uacute": "ú", "Uacute": "Ú", "agrave": "à", "Agrave": "À",
    "egrave": "è", "Egrave": "È", "igrave": "ì", "ograve": "ò",
    "ugrave": "ù", "atilde": "ã", "ntilde": "ñ", "Ntilde": "Ñ",
    "amac": "ā", "emac": "ē", "imac": "ī", "omac": "ō", "umac": "ū",
    "Amac": "Ā", "Emac": "Ē", "Imac": "Ī", "Omac": "Ō", "Umac": "Ū",
    "oelig": "œ", "OElig": "Œ", "aelig": "æ", "AElig": "Æ",
    "thorn": "þ", "Thorn": "Þ", "eth": "ð", "ETH": "Ð",
    "szlig": "ß", "acirc": "â", "ecirc": "ê", "icirc": "î",
    "ocirc": "ô", "ucirc": "û", "auml": "ä", "euml": "ë",
    "iuml": "ï", "ouml": "ö", "uuml": "ü", "yuml": "ÿ",
    "deg": "°", "sect": "§", "dagger": "†", "Dagger": "‡",
    "prime": "'", "Prime": '"', "middot": "·", "bull": "•",
    "ndash": "–", "mdash": "—", "lsquo": "'", "rsquo": "'",
    "ldquo": '"', "rdquo": '"', "amp": "&", "lt": "<", "gt": ">",
    "nbsp": " ", "copy": "©", "reg": "®", "trade": "™",
    "frac12": "½", "frac14": "¼", "frac34": "¾",
    "asl": "ă", "esl": "ĕ", "isl": "ĭ", "osl": "ŏ", "usl": "ŭ",
}

_SELF_CLOSE_RE = re.compile(r"<([a-zA-Z]+)/>")
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip(text: str) -> str:
    def _entity(m: re.Match) -> str:
        return _ENTITY_MAP.get(m.group(1), "")

    text = _SELF_CLOSE_RE.sub(_entity, text)
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def _first(tag: str, text: str) -> str | None:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL | re.IGNORECASE)
    return (_strip(m.group(1)) or None) if m else None


def _all(tag: str, text: str) -> list[str]:
    return [
        s for s in (
            _strip(m.group(1))
            for m in re.finditer(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL | re.IGNORECASE)
        )
        if s
    ]


# ---------------------------------------------------------------------------
# Entry dataclass + parser
# ---------------------------------------------------------------------------

@dataclass
class GcideEntry:
    headword: str
    part_of_speech: str | None
    definitions: list[str]
    etymology: str | None
    domain: str | None


def _parse_block(block: str) -> GcideEntry | None:
    hw_raw = _first("hw", block)
    if not hw_raw:
        return None

    headword = re.sub(r'["\']', "", hw_raw)
    headword = re.sub(r"\s*\(.*?\)", "", headword).strip()

    pos_raw = _first("pos", block)
    pos = pos_raw.rstrip(".") if pos_raw else None

    ety_m = re.search(r"<ety>(.*?)</ety>", block, re.DOTALL)
    etymology = _strip(ety_m.group(1)) if ety_m else None

    return GcideEntry(
        headword=headword,
        part_of_speech=pos,
        definitions=_all("def", block),
        etymology=etymology,
        domain=_first("fld", block),
    )


# ---------------------------------------------------------------------------
# Zip loader
# ---------------------------------------------------------------------------

_CIDE_RE = re.compile(r"gcide-[^/]+/CIDE\.[A-Z]$")
_BLOCK_RE = re.compile(r"<p>(.*?)</p>", re.DOTALL)


def _load_from_zip(path: Path) -> list[GcideEntry]:
    entries: list[GcideEntry] = []
    with zipfile.ZipFile(path) as zf:
        cide_files = sorted(n for n in zf.namelist() if _CIDE_RE.match(n))
        for fname in cide_files:
            with zf.open(fname) as fh:
                content = fh.read().decode("latin-1")
            for m in _BLOCK_RE.finditer(content):
                entry = _parse_block(m.group(1))
                if entry and entry.definitions:
                    entries.append(entry)
    return entries


# ---------------------------------------------------------------------------
# PostgreSQL writer
# ---------------------------------------------------------------------------

_WORD_SQL = """
INSERT INTO words (word, definition, historical_context, entry_type,
                   definition_source_slug, definition_source_name)
VALUES (%s, %s, %s, 'word', %s, %s)
ON CONFLICT (word) DO UPDATE SET
    definition          = COALESCE(EXCLUDED.definition,          words.definition),
    historical_context  = COALESCE(EXCLUDED.historical_context,  words.historical_context),
    definition_source_slug = COALESCE(EXCLUDED.definition_source_slug, words.definition_source_slug),
    definition_source_name = COALESCE(EXCLUDED.definition_source_name, words.definition_source_name)
RETURNING id
"""

_SENSE_SQL = """
INSERT INTO senses (
    sense_id, word_id, part_of_speech, definition, meaning_type,
    domain, era_name, first_attested_year, last_attested_year,
    source_slug, confidence, confidence_reason, evidence_grade,
    entry_headword, review_status, origin_status
) VALUES (
    %s, %s, %s, %s, 'attested',
    %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, 'reviewed', 'attested'
)
ON CONFLICT (sense_id) DO NOTHING
"""


def _write(entries: list[GcideEntry], dry_run: bool = False) -> ImportResult:
    result = ImportResult(dry_run=dry_run)

    if dry_run:
        for e in entries[:10]:
            defn = (e.definitions[0] if e.definitions else "")[:80]
            print(f"  [dry_run] {e.headword!r:<30} pos={e.part_of_speech!r:<12} def={defn!r}")
        result.ingested = len(entries)
        return result

    conn = psycopg2.connect(SYNC_URL)
    try:
        cur = conn.cursor()
        for i, entry in enumerate(entries):
            word = entry.headword.lower()
            defn_primary = entry.definitions[0] if entry.definitions else None
            try:
                cur.execute(_WORD_SQL, (
                    word, defn_primary, entry.etymology,
                    SOURCE_SLUG, "Webster's 1913",
                ))
                row = cur.fetchone()
                if not row:
                    result.skipped += 1
                    continue
                word_id = row[0]
            except Exception as exc:
                result.failed += 1
                result.errors.append(f"{word}: {exc}")
                conn.rollback()
                continue

            for idx, defn in enumerate(entry.definitions):
                sense_id = f"{word}-late-modern-gcide-{i}-{idx}"
                try:
                    cur.execute(_SENSE_SQL, (
                        sense_id, word_id, entry.part_of_speech, defn,
                        entry.domain, ERA_NAME, FIRST_YEAR, LAST_YEAR,
                        SOURCE_SLUG, CONFIDENCE, CONFIDENCE_REASON, EVIDENCE_GRADE,
                        entry.headword,
                    ))
                except Exception as exc:
                    result.errors.append(f"{sense_id}: {exc}")
                    conn.rollback()

            result.ingested += 1

            if (i + 1) % 500 == 0:
                conn.commit()
                pct = (i + 1) / len(entries) * 100
                print(f"\r  progress: {i+1:,}/{len(entries):,} ({pct:.1f}%)", end="", flush=True)

        conn.commit()
        print()
    finally:
        conn.close()

    return result


# ---------------------------------------------------------------------------
# BaseImporter subclass
# ---------------------------------------------------------------------------

class GcideImporter(BaseImporter):
    source_name = "gcide"
    cli_description = "Import words and senses from the GCIDE (Webster's 1913) zip."
    default_path = Path("Words/gcide-0.54.zip")

    def load(self, path: Path) -> list[Any]:
        print(f"[gcide] Parsing {path} …")
        raw = _load_from_zip(path)
        valid = [
            e for e in raw
            if is_valid_word(e.headword.lower(), include_phrases=False)
        ]
        print(f"[gcide] {len(raw):,} total blocks; {len(valid):,} valid single words")
        return valid

    def ingest(self, records: list[Any], *, dry_run: bool = False) -> ImportResult:
        return _write(records, dry_run=dry_run)


if __name__ == "__main__":
    GcideImporter().run_cli()
