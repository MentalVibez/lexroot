"""
WiktionaryAgent — async agent that fetches etymology and IPA phonemes from
the Wiktionary REST API for words not covered by the etymwn or Collins agents.

Rate limiting: token-bucket at `rate_limit` req/s with exponential backoff on
429 responses. Respects the Retry-After header when present.
Checkpoint file allows resuming interrupted runs.

API used:
  GET https://en.wiktionary.org/w/api.php
    ?action=query&titles={word}&prop=revisions&rvprop=content&format=json
  — Returns raw wikitext; we extract ==Etymology== and phonemes from it.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from pathlib import Path

import httpx

from ingestor.etymology_agents.base import EtymologyRecord

_API = "https://en.wiktionary.org/w/api.php"
_PARAMS = "action=query&prop=revisions&rvprop=content&format=json&titles={word}"

_MAX_RETRIES = 5
_BACKOFF_BASE = 2.0   # seconds; doubles each attempt

# Extract IPA from {{IPA|en|/.../ }} or {{IPA|/.../ }}
_IPA_RE = re.compile(r"\{\{IPA[^}]*?[|/]([^/}{|]+?)/")

# Etymology section header (level 2 or 3)
_ETYM_SECTION_RE = re.compile(
    r"={2,3}Etymology[^=]*={2,3}(.*?)(?===|\Z)", re.DOTALL
)

# Common wiki templates to strip: {{m|la|word}}, {{der|en|la|word}}, etc.
_WIKI_LINK_RE = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]")
_WIKI_TMPL_RE = re.compile(r"\{\{[^}]+\}\}")
_WIKI_TAG_RE = re.compile(r"<[^>]+>")


class _TokenBucket:
    """Thread-safe token bucket enforcing a steady `rate` requests/second."""

    def __init__(self, rate: float) -> None:
        self._rate = rate
        self._tokens = rate
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                self._tokens = min(
                    self._rate,
                    self._tokens + (now - self._last) * self._rate,
                )
                self._last = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self._rate
            await asyncio.sleep(wait)


def _clean_wikitext(text: str) -> str:
    text = _WIKI_LINK_RE.sub(r"\1", text)
    text = _WIKI_TMPL_RE.sub("", text)
    text = _WIKI_TAG_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^[,.:;]+\s*", "", text)
    return text[:500] if len(text) > 500 else text


def _parse_wikitext(word: str, wikitext: str) -> EtymologyRecord | None:
    """Extract IPA and etymology section from raw wikitext."""
    if not wikitext:
        return None

    ipa_match = _IPA_RE.search(wikitext)
    phonemes = f"/{ipa_match.group(1).strip()}/" if ipa_match else None

    etym_match = _ETYM_SECTION_RE.search(wikitext)
    historical_context = None
    if etym_match:
        cleaned = _clean_wikitext(etym_match.group(1).strip())
        if len(cleaned) > 20:
            historical_context = cleaned

    if not phonemes and not historical_context:
        return None

    return EtymologyRecord(
        word=word,
        phonemes=phonemes,
        historical_context=historical_context,
        confidence="medium",
        source_agent="wiktionary",
    )


class WiktionaryAgent:
    """
    Fetches phonemes and etymology text from Wiktionary for a list of words.
    Uses a token-bucket rate limiter and retries with exponential backoff on
    429 responses. Results are checkpointed to disk so interrupted runs resume.
    """

    def __init__(
        self,
        checkpoint_path: Path | None = None,
        concurrency: int = 25,
        rate_limit: float = 30.0,     # conservative default; Wiktionary allows ~200/s
    ):
        self.checkpoint_path = checkpoint_path or Path("Words/.wiktionary_checkpoint.json")
        self.concurrency = concurrency
        self.rate_per_second = rate_limit
        self._cache: dict[str, EtymologyRecord | None] = {}

    def _load_checkpoint(self) -> None:
        if self.checkpoint_path.exists():
            with self.checkpoint_path.open(encoding="utf-8") as f:
                raw = json.load(f)
            for word, data in raw.items():
                self._cache[word] = EtymologyRecord(**data) if data else None
            print(f"[wiktionary] Checkpoint: {len(self._cache):,} words already cached")

    def _save_checkpoint(self) -> None:
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        serialised = {
            w: (vars(r) if r else None)
            for w, r in self._cache.items()
        }
        with self.checkpoint_path.open("w", encoding="utf-8") as f:
            json.dump(serialised, f)

    async def _fetch_one(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        bucket: _TokenBucket,
        word: str,
    ) -> tuple[str, EtymologyRecord | None]:
        url = f"{_API}?{_PARAMS.format(word=word)}"

        async with semaphore:
            for attempt in range(_MAX_RETRIES):
                await bucket.acquire()
                try:
                    resp = await client.get(url, timeout=15.0)

                    if resp.status_code == 429:
                        # Honour Retry-After if present; otherwise exponential backoff
                        retry_after = float(
                            resp.headers.get("Retry-After", _BACKOFF_BASE ** attempt)
                        )
                        print(
                            f"[wiktionary] 429 on '{word}' — "
                            f"backing off {retry_after:.1f}s (attempt {attempt + 1})",
                            file=sys.stderr,
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    resp.raise_for_status()
                    data = resp.json()
                    pages = data.get("query", {}).get("pages", {})
                    for page in pages.values():
                        revisions = page.get("revisions", [])
                        if revisions:
                            wikitext = (
                                revisions[0].get("*", "")
                                or revisions[0]
                                .get("slots", {})
                                .get("main", {})
                                .get("*", "")
                            )
                            return word, _parse_wikitext(word, wikitext)
                    return word, None  # page exists but no revisions

                except httpx.HTTPStatusError as e:
                    print(f"[wiktionary] HTTP {e.response.status_code} on '{word}'", file=sys.stderr)
                    break  # non-429 HTTP error; don't retry
                except Exception as e:
                    wait = _BACKOFF_BASE ** attempt
                    print(f"[wiktionary] '{word}' attempt {attempt + 1}: {e} — retry in {wait:.1f}s", file=sys.stderr)
                    await asyncio.sleep(wait)

        return word, None

    async def fetch_batch(self, words: list[str]) -> dict[str, EtymologyRecord]:
        uncached = [w for w in words if w.lower() not in self._cache]
        if not uncached:
            return {w: r for w, r in self._cache.items() if r is not None}

        print(
            f"[wiktionary] Fetching {len(uncached):,} words "
            f"(concurrency={self.concurrency}, rate={self.rate_per_second}/s) …"
        )

        semaphore = asyncio.Semaphore(self.concurrency)
        bucket = _TokenBucket(self.rate_per_second)
        results: dict[str, EtymologyRecord] = {}
        done = 0

        async with httpx.AsyncClient(
            headers={"User-Agent": "LivingLexiconBot/1.0 (etymology pipeline; contact via GitHub)"}
        ) as client:
            tasks = [
                self._fetch_one(client, semaphore, bucket, w)
                for w in uncached
            ]
            for coro in asyncio.as_completed(tasks):
                word, record = await coro
                self._cache[word.lower()] = record
                if record:
                    results[word] = record
                done += 1
                if done % 500 == 0:
                    pct = done / len(uncached) * 100
                    print(f"\r  {done:,}/{len(uncached):,} ({pct:.1f}%)", end="", flush=True)
                    self._save_checkpoint()

        self._save_checkpoint()
        print(f"\r  {done:,}/{len(uncached):,} (100.0%)  — done        ")
        return results

    def run(self, words: list[str]) -> dict[str, EtymologyRecord]:
        self._load_checkpoint()
        return asyncio.run(self.fetch_batch(words))
