"""
EtymWordNet Importer — bulk-loads English etymology data from Words/etymwn.tsv.

etymwn.tsv format (tab-separated):
  source_lang: source_word  <TAB>  rel:relationship_type  <TAB>  target_lang: target_word

This importer extracts two types of relationships:
  1. ROOT DERIVATION: OldEnglish/ProtoGermanic/OldNorse/Latin/Greek/OldFrench → English word
     e.g. "lat: convenire  rel:etymological_origin_of  eng: convene"
  2. ENGLISH COGNATES: English word → etymologically_related → English word
     e.g. "eng: convene  rel:etymologically_related  eng: convention"

Usage:
  python -m ingestor.etymwn_importer --limit 5000
  python -m ingestor.etymwn_importer --all-source-langs --limit 0
  python -m ingestor.etymwn_importer --lang lat --limit 2000
  python -m ingestor.etymwn_importer --word compassion
"""
import argparse
import os
import re
from collections import defaultdict

try:
    import nltk
    from nltk.corpus import wordnet as wn
    _NLTK_AVAILABLE = True
except ImportError:
    _NLTK_AVAILABLE = False

from ingestor.graph_loader import EtymologyClaim, LexiconIngestor, WordEntry
from ingestor.sources_catalog import ALL_SOURCES


ETYMWN_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "Words", "etymwn.tsv"
)

# Map EtymWordNet ISO 639-3 codes → human-readable root origin language
LANG_CODE_MAP = {
    "eng": "English",
    "lat": "Classical Latin",
    "grc": "Ancient Greek",
    "ang": "Old English",
    "enm": "Middle English",
    "fro": "Old French",
    "non": "Old Norse",
    "gmh": "Middle High German",
    "dum": "Middle Dutch",
    "pie": "Proto-Indo-European",
    "pro": "Old Occitan",
    "frk": "Frankish",
    "gem": "Proto-Germanic",
    "ine": "Proto-Indo-European",
    "fra": "French",
    "frm": "Middle French",
    "deu": "German",
    "ita": "Italian",
    "spa": "Spanish",
    "ara": "Arabic",
    "san": "Sanskrit",
    "heb": "Hebrew",
    "rus": "Russian",
    "nld": "Dutch",
    "por": "Portuguese",
    "jpn": "Japanese",
    "tur": "Turkish",
    "yid": "Yiddish",
    "msa": "Malay",
    "hin": "Hindi",
    "fas": "Persian",
    "gle": "Irish",
    "hye": "Armenian",
    "cmn": "Mandarin Chinese",
    "sco": "Scots",
    "ell": "Greek",
    "xno": "Anglo-Norman",
}

ETYMWN_SOURCE_SLUG = "etymwordnet"

# English is a West Germanic language. When EtymWordNet provides several
# possible source forms, prefer inherited English/Germanic ancestry first.
# Romance/Latin/Greek candidates remain valid, but should win only when no
# closer Germanic source is present.
ROOT_SOURCE_PRIORITY = {
    "English": 0,
    "Old English": 1,
    "Middle English": 2,
    "Proto-Germanic": 3,
    "Old Norse": 4,
    "Frankish": 5,
    "Middle High German": 6,
    "Middle Dutch": 7,
    "German": 8,
    "Dutch": 9,
    "Scots": 10,
    "Proto-Indo-European": 20,
    "Classical Latin": 30,
    "Old French": 31,
    "Anglo-Norman": 32,
    "French": 33,
    "Middle French": 34,
    "Ancient Greek": 35,
}
_ALL_SOURCE_LANG = "*"

# Relationship types that express "source gave rise to English word"
ROOT_RELATIONS = {"rel:etymological_origin_of"}
# Relationship types that express "these English words share ancestry"
COGNATE_RELATIONS = {"rel:etymologically_related"}
# These inflate the graph with inflectional noise (plurals, past tenses) — skip them
SKIP_RELATIONS = {"rel:has_derived_form", "rel:is_derived_from", "rel:variant:orthography"}

_CLEAN_WORD = re.compile(r"^[a-z][a-z'\-]{1,29}$")


def _is_clean_english_word(word: str) -> bool:
    """Only import clean, simple English words — no brackets, phrases, or symbols."""
    return bool(_CLEAN_WORD.match(word.casefold()))


def _language_name(code: str) -> str:
    return LANG_CODE_MAP.get(code, f"ISO 639-3: {code}")


def _clean_root_word(raw: str) -> str:
    """Strip Wiki-markup and take the first clean token from a root form."""
    # Remove [[ ]] brackets: [[venire]] → venire
    cleaned = re.sub(r"\[\[([^\]]+)\]\]", r"\1", raw)
    # Take only the first word if it's a phrase
    first = cleaned.strip().split()[0].strip("'\".,;:()[]")
    return first.lower()


def _get_definition(word: str) -> str:
    """Fetch the first WordNet definition for an English word, or empty string."""
    if not _NLTK_AVAILABLE:
        return ""
    synsets = wn.synsets(word, lang="eng")
    if synsets:
        return synsets[0].definition()
    return ""


def _ensure_nltk():
    if not _NLTK_AVAILABLE:
        print("[etymwn] nltk not installed — definitions will be empty.")
        print("         Run: pip install nltk && python -c \"import nltk; nltk.download('wordnet')\"")
        return
    try:
        wn.synsets("test")
    except LookupError:
        print("[etymwn] Downloading NLTK WordNet corpus…")
        nltk.download("wordnet", quiet=True)
        nltk.download("omw-1.4", quiet=True)


def parse_etymwn(
    target_langs: list[str] | None = None,
    target_word: str | None = None,
    limit: int | None = 5000,
) -> tuple[list[dict], dict[str, list[str]]]:
    """
    Parse etymwn.tsv and return:
      - derivations: list of {eng_word, root_word, root_lang, root_origin_language}
      - cognate_map: {eng_word: [cognate1, cognate2, ...]}

    Args:
        target_langs: filter to specific source languages, e.g. ["lat", "grc"].
                      None = all supported languages.
        target_word:  if set, extract ALL relationships for this specific word only.
        limit:        max derivations to collect (not counting cognates). None = no limit.
    """
    collect_all_source_langs = bool(target_langs and _ALL_SOURCE_LANG in target_langs)
    langs = set(target_langs or LANG_CODE_MAP.keys())
    derivations = []
    cognate_map: dict[str, list[str]] = defaultdict(list)
    seen_pairs: set[tuple[str, str]] = set()

    with open(ETYMWN_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue

            src_raw, rel, tgt_raw = parts
            rel = rel.strip()

            # Parse "lang: word" tokens
            def split_token(tok: str) -> tuple[str, str] | None:
                tok = tok.strip()
                if ": " not in tok:
                    return None
                lang, word = tok.split(": ", 1)
                return lang.strip(), word.strip().lower()

            src = split_token(src_raw)
            tgt = split_token(tgt_raw)
            if not src or not tgt:
                continue

            src_lang, src_word = src
            tgt_lang, tgt_word = tgt

            if target_word:
                # Single-word mode: collect everything about this word
                if src_word != target_word and tgt_word != target_word:
                    continue
            else:
                if limit is not None and len(derivations) >= limit:
                    # Still need to process cognate lines even past the limit
                    if rel not in COGNATE_RELATIONS or tgt_lang != "eng" or src_lang != "eng":
                        continue

            # ROOT DERIVATION: source_lang → rel:etymological_origin_of → eng: word
            if (
                rel in ROOT_RELATIONS
                and tgt_lang == "eng"
                and (collect_all_source_langs or src_lang in langs)
            ):
                eng_word = tgt_word.casefold()
                root_word = _clean_root_word(src_word)
                if not _is_clean_english_word(eng_word) or not root_word:
                    continue
                pair = (eng_word, root_word)
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    derivations.append({
                        "eng_word": eng_word,
                        "root_word": root_word,
                        "root_lang": src_lang,
                        "root_origin_language": _language_name(src_lang),
                    })

            # ENGLISH COGNATES: eng: word → etymologically_related → eng: word
            elif rel in COGNATE_RELATIONS and src_lang == "eng" and tgt_lang == "eng":
                src_word = src_word.casefold()
                tgt_word = tgt_word.casefold()
                if _is_clean_english_word(src_word) and _is_clean_english_word(tgt_word):
                    if tgt_word not in cognate_map[src_word]:
                        cognate_map[src_word].append(tgt_word)

    return derivations, dict(cognate_map)


def build_word_entries(
    derivations: list[dict],
    cognate_map: dict[str, list[str]],
) -> list[WordEntry]:
    """Convert parsed EtymWordNet rows into WordEntry objects ready for Neo4j ingestion."""
    _ensure_nltk()

    # Group derivations by English word (a word may have multiple root sources)
    by_word: dict[str, list[dict]] = defaultdict(list)
    for d in derivations:
        by_word[d["eng_word"]].append(d)

    entries = []
    for eng_word, sources in by_word.items():
        # Pick the closest source without turning English into a Romance-first language.
        best = min(sources, key=lambda s: ROOT_SOURCE_PRIORITY.get(s["root_origin_language"], 99))

        definition = _get_definition(eng_word)
        cognates = cognate_map.get(eng_word, [])[:10]

        entries.append(WordEntry(
            name=eng_word,
            language="English",
            definition=definition or f"(no definition — search '{eng_word}' to enrich)",
            root_name=best["root_word"],
            root_meaning="",  # etymwn doesn't provide root meanings; Wiktionary scraper fills these
            root_origin_language=best["root_origin_language"],
            cognates=cognates,
            etymology_claims=[
                EtymologyClaim(
                    source_form=best["root_word"],
                    source_language=best["root_origin_language"],
                    relation_type="etymological_origin_of",
                    source_slug=ETYMWN_SOURCE_SLUG,
                    confidence="medium",
                    note="Machine-readable EtymWordNet derivation; root meaning pending scholarly review.",
                    is_reconstructed=best["root_origin_language"].startswith("Proto-") or best["root_word"].startswith("*"),
                )
            ],
            era_meanings=[
                {
                    "era_name": "Modern English",
                    "meaning": definition or f"EtymWordNet-derived lexical entry for '{eng_word}'.",
                    "usage_example": None,
                    "register": "general",
                    "source": ETYMWN_SOURCE_SLUG,
                    "confidence": "medium",
                }
            ],
        ))

    return entries


def import_from_etymwn(
    target_langs: list[str] | None = None,
    target_word: str | None = None,
    limit: int | None = 5000,
    dry_run: bool = False,
) -> dict:
    """
    Full pipeline: parse etymwn.tsv → build WordEntry objects → ingest into Neo4j.

    Args:
        target_langs: filter to specific source languages (ISO 639-3 codes)
        target_word:  import a single word with all its relationships
        limit:        max English words to import. None = no limit.
        dry_run:      parse and print without writing to Neo4j
    """
    print(f"[etymwn] Parsing {ETYMWN_PATH}…")
    derivations, cognate_map = parse_etymwn(target_langs, target_word, limit)
    print(f"[etymwn] Found {len(derivations)} derivations, {len(cognate_map)} cognate groups")

    entries = build_word_entries(derivations, cognate_map)
    print(f"[etymwn] Built {len(entries)} WordEntry objects")

    if dry_run:
        for e in entries[:10]:
            print(f"  {e.name} ← {e.root_name} ({e.root_origin_language})"
                  f" | cognates: {e.cognates[:3]} | def: {e.definition[:60]}")
        print("  [dry_run] — no data written")
        return {"entries": len(entries), "dry_run": True}

    ingestor = LexiconIngestor()
    ingestor.ensure_indexes()
    for source in ALL_SOURCES:
        if source["slug"] == ETYMWN_SOURCE_SLUG:
            ingestor.ingest_source(source)
            break
    results = ingestor.bulk_ingest(entries)
    for entry in entries:
        try:
            ingestor.write_attested_in(entry.name, entry.language, ETYMWN_SOURCE_SLUG)
        except Exception:
            pass
    ingestor.close()

    print(f"[etymwn] Done — ingested={results['ingested']}, failed={results['failed']}")
    if results["errors"]:
        for err in results["errors"][:5]:
            print(f"  ERROR: {err['word']}: {err['error']}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import EtymWordNet data into the Living Lexicon")
    parser.add_argument("--lang", nargs="+",
                        help="Source language codes to include (e.g. lat grc ang). Default: all supported.",
                        choices=list(LANG_CODE_MAP.keys()))
    parser.add_argument("--word", help="Import a single specific English word")
    parser.add_argument("--limit", type=int, default=5000,
                        help="Max number of English words to import. Use 0 for no limit (default: 5000)")
    parser.add_argument("--all-source-langs", action="store_true",
                        help="Import English derivations from every EtymWordNet source language, not only curated language codes.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and preview without writing to Neo4j")
    args = parser.parse_args()

    limit = None if args.limit == 0 else args.limit
    langs = [_ALL_SOURCE_LANG] if args.all_source_langs else args.lang

    import_from_etymwn(
        target_langs=langs,
        target_word=args.word,
        limit=limit,
        dry_run=args.dry_run,
    )
