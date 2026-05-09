"""
HTTP implementation of EtymologyStore.
Calls a remote Living Lexicon API server — powers WordHistorian.from_url().
Any project can point at a shared instance without running Neo4j locally.
"""
from __future__ import annotations
import httpx


class HttpStore:
    """EtymologyStore backed by a remote Living Lexicon REST API."""

    def __init__(self, base_url: str, timeout: float = 10.0):
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def ping(self) -> bool:
        try:
            r = self._client.get("/health", timeout=3.0)
            data = r.json()
            return data.get("neo4j") == "ready"
        except Exception:
            return False

    # ── Word queries ──────────────────────────────────────────────────────────

    def get_word(self, word: str) -> dict | None:
        r = self._client.get(f"/word/{word}")
        return r.json() if r.status_code == 200 else None

    def get_word_tree(self, word: str) -> dict:
        r = self._client.get(f"/word/{word}/tree")
        return r.json() if r.status_code == 200 else {}

    def get_cognates(self, word: str) -> list[dict]:
        r = self._client.get(f"/word/{word}/cognates")
        return r.json().get("cognates", []) if r.status_code == 200 else []

    def get_etymology_claims(self, word: str) -> list[dict]:
        r = self._client.get(f"/word/{word}/etymology-claims")
        return r.json().get("claims", []) if r.status_code == 200 else []

    def search(self, query: str, limit: int = 10) -> list[dict]:
        r = self._client.get("/search", params={"q": query, "limit": limit})
        return r.json().get("results", []) if r.status_code == 200 else []

    # ── Era queries ───────────────────────────────────────────────────────────

    def get_word_era_meanings(self, word: str) -> list[dict]:
        # Not exposed as a direct endpoint; approximate via era-timeline
        r = self._client.get(f"/word/{word}/era-timeline")
        return r.json().get("timeline", []) if r.status_code == 200 else []

    def get_era_timeline(self, word: str) -> list[dict]:
        r = self._client.get(f"/word/{word}/era-timeline")
        return r.json().get("timeline", []) if r.status_code == 200 else []

    def get_word_in_era(self, word: str, era_name: str) -> dict | None:
        r = self._client.get(f"/word/{word}/era/{era_name}")
        return r.json() if r.status_code == 200 else None

    def get_era_by_year(self, year: int) -> dict | None:
        r = self._client.get(f"/era/by-year/{year}")
        return r.json() if r.status_code == 200 else None

    def get_words_by_era(self, era_name: str, limit: int = 20) -> list[dict]:
        r = self._client.get(f"/era/{era_name}/words", params={"limit": limit})
        return r.json().get("words", []) if r.status_code == 200 else []

    # ── Source queries ────────────────────────────────────────────────────────

    def get_all_sources(self) -> list[dict]:
        r = self._client.get("/sources")
        return r.json().get("sources", []) if r.status_code == 200 else []

    def get_source(self, slug: str) -> dict | None:
        r = self._client.get(f"/sources/{slug}")
        return r.json() if r.status_code == 200 else None

    def get_word_sources(self, word: str) -> list[dict]:
        r = self._client.get(f"/word/{word}/sources")
        return r.json().get("sources", []) if r.status_code == 200 else []

    def get_words_by_source(self, slug: str, limit: int = 20) -> list[dict]:
        r = self._client.get(f"/sources/{slug}/words", params={"limit": limit})
        return r.json().get("words", []) if r.status_code == 200 else []
