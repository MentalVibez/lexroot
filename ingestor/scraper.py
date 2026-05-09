"""
Wiktionary etymology scraper.
Parses the English Wiktionary page for a word and extracts:
  - definition, etymology section, cognates, root language
Usage:
  python -m ingestor.scraper compassion patience passion
"""
import asyncio
import re
import sys
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup, Tag

from ingestor.graph_loader import LexiconIngestor, WordEntry


WIKTIONARY_URL = "https://en.wiktionary.org/wiki/{word}"

# PIE/Latin/Greek root patterns found in Wiktionary etymology text
_ROOT_PATTERNS = [
    r"from (?:Proto-Indo-European|PIE) \*?(\w+)",
    r"from (?:Latin|Old Latin) (\w+)",
    r"from (?:Ancient Greek|Greek) (\w+)",
    r"from (?:Old French|French) (\w+)",
    r"from (?:Old English) (\w+)",
]

# Words commonly listed as "related terms" or "cognates" on Wiktionary
_COGNATE_SECTION_HEADERS = {"related terms", "cognates", "derived terms"}


@dataclass
class ScrapedEntry:
    word: str
    language: str = "English"
    definition: str = ""
    etymology_text: str = ""
    root_name: str = ""
    root_meaning: str = ""
    root_origin_language: str = "Proto-Indo-European"
    cognates: list[str] = field(default_factory=list)


async def scrape_word(word: str) -> ScrapedEntry | None:
    url = WIKTIONARY_URL.format(word=word.lower())
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            print(f"[scraper] HTTP error for '{word}': {e}")
            return None

    soup = BeautifulSoup(resp.text, "html.parser")
    entry = ScrapedEntry(word=word)

    _extract_definition(soup, entry)
    _extract_etymology(soup, entry)
    _extract_cognates(soup, entry)

    if not entry.root_name:
        entry.root_name = word  # fallback: treat the word itself as its own root node

    return entry


def _extract_definition(soup: BeautifulSoup, entry: ScrapedEntry):
    # Wiktionary definitions are in <ol> following a POS heading (Noun, Verb, etc.)
    pos_headings = soup.find_all(["h3", "h4"], string=re.compile(r"Noun|Verb|Adjective"))
    for heading in pos_headings:
        ol = heading.find_next("ol")
        if ol:
            first_li = ol.find("li")
            if first_li:
                entry.definition = first_li.get_text(" ", strip=True)[:500]
                return


def _extract_etymology(soup: BeautifulSoup, entry: ScrapedEntry):
    etym_heading = soup.find(["h3", "h4"], string=re.compile(r"Etymology"))
    if not etym_heading:
        return

    p = etym_heading.find_next("p")
    if not p:
        return

    entry.etymology_text = p.get_text(" ", strip=True)

    for pattern in _ROOT_PATTERNS:
        match = re.search(pattern, entry.etymology_text, re.IGNORECASE)
        if match:
            entry.root_name = match.group(1).strip("*").lower()
            # Detect origin language from the pattern text
            for lang in ("Proto-Indo-European", "PIE", "Latin", "Ancient Greek", "Old French", "Old English"):
                if lang.lower() in match.group(0).lower():
                    entry.root_origin_language = lang.replace("PIE", "Proto-Indo-European")
                    break
            # Try to extract meaning from parenthetical e.g. "from Latin pati (to suffer)"
            meaning_match = re.search(
                r'\(' + re.escape(entry.root_name) + r'[^)]*?[,\s]+"?([^")]+)"?\)',
                entry.etymology_text,
                re.IGNORECASE,
            )
            if meaning_match:
                entry.root_meaning = meaning_match.group(1).strip()
            break


def _extract_cognates(soup: BeautifulSoup, entry: ScrapedEntry):
    for header in soup.find_all(["h3", "h4", "h5"]):
        if header.get_text(strip=True).lower() in _COGNATE_SECTION_HEADERS:
            ul = header.find_next("ul")
            if ul:
                for li in ul.find_all("li")[:10]:
                    text = li.get_text(" ", strip=True)
                    # Pull the first linked word as the cognate
                    link = li.find("a")
                    if link and link.get_text(strip=True).isalpha():
                        entry.cognates.append(link.get_text(strip=True).lower())


def to_word_entry(scraped: ScrapedEntry) -> WordEntry:
    return WordEntry(
        name=scraped.word.lower(),
        language=scraped.language,
        definition=scraped.definition,
        root_name=scraped.root_name or scraped.word.lower(),
        root_meaning=scraped.root_meaning or "meaning unknown",
        root_origin_language=scraped.root_origin_language,
        cognates=scraped.cognates,
    )


async def scrape_and_ingest(words: list[str]):
    ingestor = LexiconIngestor()
    ingestor.ensure_indexes()
    print(f"[scraper] Scraping {len(words)} word(s)...")

    entries = []
    for word in words:
        print(f"[scraper] Fetching '{word}'...")
        scraped = await scrape_word(word)
        if scraped:
            entries.append(to_word_entry(scraped))
            print(f"  root={scraped.root_name!r}, cognates={scraped.cognates[:3]}")

    results = ingestor.bulk_ingest(entries)
    ingestor.close()
    print(f"[scraper] Done — ingested={results['ingested']}, failed={results['failed']}")
    if results["errors"]:
        for err in results["errors"]:
            print(f"  ERROR: {err}")


if __name__ == "__main__":
    words = sys.argv[1:] or ["compassion", "patient", "passion", "hospital", "hostile"]
    asyncio.run(scrape_and_ingest(words))
