"""
CollinsHintAgent — extracts origin language from parenthetical hints at the
start of Collins definitions, e.g. "(Hawaiian)", "(Latin)", "(South African)".

This is a fast, zero-API supplement to the etymwn agent for words where
Collins' definition explicitly names the source language but etymwn has no
entry.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from ingestor.etymology_agents.base import COLLINS_HINT_TO_LANGUAGE, EtymologyRecord

MASTER_LEXICON = Path(__file__).parent.parent.parent / "Words" / "english_words_master_lexicon.csv"

_HINT_RE = re.compile(r"^\(([A-Za-z][A-Za-z\s\-]+?)\)\s")


def _extract_hint(definition: str) -> str | None:
    m = _HINT_RE.match(definition)
    return m.group(1).strip() if m else None


class CollinsHintAgent:
    """
    Builds a word → (origin_language, language_family) map from the master
    lexicon's definition column in one pass, then serves O(1) lookups.
    """

    def __init__(self, path: Path = MASTER_LEXICON):
        self.path = path
        self._index: dict[str, tuple[str, str]] = {}
        self._loaded = False

    def load(self, verbose: bool = True) -> None:
        if self._loaded:
            return
        if not self.path.exists():
            print(f"[collins] WARNING: {self.path} not found.", file=sys.stderr)
            return

        hits = 0
        with self.path.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                word = row.get("word", "").strip()
                defn = row.get("definition", "").strip()
                if not word or not defn:
                    continue
                hint = _extract_hint(defn)
                if hint and hint in COLLINS_HINT_TO_LANGUAGE:
                    self._index[word.lower()] = COLLINS_HINT_TO_LANGUAGE[hint]
                    hits += 1

        self._loaded = True
        if verbose:
            print(f"[collins] {hits:,} words with recognisable language hints")

    def lookup(self, word: str) -> EtymologyRecord | None:
        result = self._index.get(word.lower())
        if not result:
            return None
        lang_name, lang_family = result
        canonical = word[0].upper() + word[1:].lower() if word else word
        return EtymologyRecord(
            word=canonical,
            origin_language=lang_name,
            language_family=lang_family,
            historical_context=f"Derived from {lang_name}.",
            confidence="medium",
            source_agent="collins_hint",
        )

    def batch_lookup(self, words: list[str]) -> dict[str, EtymologyRecord]:
        return {w: r for w in words if (r := self.lookup(w)) is not None}

    @property
    def coverage(self) -> int:
        return len(self._index)
