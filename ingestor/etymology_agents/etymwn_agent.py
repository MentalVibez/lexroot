"""
EtymwnAgent — builds an in-memory index from etymwn.tsv then serves
O(1) etymology lookups for English words.

etymwn.tsv format (tab-separated, ~6M rows):
  SOURCE_LANG: SOURCE_WORD  <TAB>  RELATION  <TAB>  TARGET_LANG: TARGET_WORD

Relations used here:
  rel:etymological_origin_of   → source gave origin to target English word
  rel:is_derived_from          → English word derived from source
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from ingestor.etymology_agents.base import ISO_TO_LANGUAGE, EtymologyRecord

ETYMWN_PATH = Path(__file__).parent.parent.parent / "Words" / "etymwn.tsv"

# Relation priority: lower = better evidence
_REL_PRIORITY = {
    "rel:etymological_origin_of": 0,
    "rel:is_derived_from":        1,
    "rel:etymologically_related": 2,
    "rel:etymology":              3,
}

# Only skip modern English → modern English (trivial self-derivation).
# Keep enm (Middle English) and ang (Old English) — they're genuine origins.
_SKIP_SELF_LANGS = {"eng"}


def _parse_node(node: str) -> tuple[str, str]:
    """'lat: vocabulum' → ('lat', 'vocabulum')"""
    parts = node.split(": ", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return "", node.strip()


class EtymwnAgent:
    """
    Index structure: eng_lower_word → list of (priority, source_lang, source_word)
    The best candidate is the one with lowest priority value from a non-English source.
    """

    def __init__(self, path: Path = ETYMWN_PATH):
        self.path = path
        # eng_word → [(priority, source_lang, source_word)]
        self._index: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
        self._loaded = False

    def load(self, verbose: bool = True) -> None:
        if self._loaded:
            return
        if not self.path.exists():
            print(f"[etymwn] WARNING: {self.path} not found — agent disabled.", file=sys.stderr)
            return

        if verbose:
            print(f"[etymwn] Loading {self.path.name} (~6M rows) …", flush=True)

        count = 0
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) != 3:
                    continue
                src_node, rel, tgt_node = parts
                priority = _REL_PRIORITY.get(rel, 99)
                if priority == 99:
                    continue

                src_lang, src_word = _parse_node(src_node)
                tgt_lang, tgt_word = _parse_node(tgt_node)

                # Case 1: X etymological_origin_of eng:word
                if tgt_lang == "eng" and rel == "rel:etymological_origin_of":
                    eng_key = tgt_word.lower()
                    if src_lang not in _SKIP_SELF_LANGS:
                        self._index[eng_key].append((priority, src_lang, src_word))
                        count += 1

                # Case 2: eng:word is_derived_from X
                elif src_lang == "eng" and rel == "rel:is_derived_from":
                    eng_key = src_word.lower()
                    if tgt_lang not in _SKIP_SELF_LANGS:
                        self._index[eng_key].append((priority, tgt_lang, tgt_word))
                        count += 1

        self._loaded = True
        if verbose:
            print(f"[etymwn] Index built: {len(self._index):,} English words  ({count:,} relations)")

    def lookup(self, word: str) -> EtymologyRecord | None:
        candidates = self._index.get(word.lower())
        if not candidates:
            return None

        # Pick best: lowest priority, prefer non-English source
        best = min(candidates, key=lambda c: (c[0], c[1] in _SKIP_SELF_LANGS))
        _, src_lang, src_word = best

        lang_name, lang_family = ISO_TO_LANGUAGE.get(src_lang, (src_lang, "Unknown"))
        canonical_word = word[0].upper() + word[1:].lower() if word else word

        context = f"Derived from {lang_name} '{src_word}'."
        if src_lang in ("lat", "grc"):
            context = f"From {lang_name} '{src_word}'."
        elif src_lang in ("ang",):
            context = f"From Old English '{src_word}'."
        elif src_lang in ("fro", "xno"):
            context = f"Entered English via {lang_name} '{src_word}' after the Norman Conquest."
        elif src_lang in ("non",):
            context = f"From Old Norse '{src_word}', entering English via Viking contact."

        return EtymologyRecord(
            word=canonical_word,
            etymology_root=src_word,
            origin_language=lang_name,
            language_family=lang_family,
            historical_context=context,
            confidence="high",
            source_agent="etymwn",
        )

    def batch_lookup(self, words: list[str]) -> dict[str, EtymologyRecord]:
        return {w: r for w in words if (r := self.lookup(w)) is not None}

    @property
    def coverage(self) -> int:
        return len(self._index)
