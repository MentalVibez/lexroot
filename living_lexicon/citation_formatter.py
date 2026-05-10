"""
Citation formatter for Living Lexicon sense records.

Produces academic citation strings in BibTeX, APA, MLA, and Chicago formats
from a Sense ORM object. No database access — pure string transformation.

Usage:
    from living_lexicon.citation_formatter import to_bibtex, to_apa, to_mla, to_chicago
    raw = to_bibtex(sense, access_url="https://example.com/pg/sense/my-sense-id")
"""
from __future__ import annotations

import re

# Source metadata lookup — keyed by slug for O(1) author resolution
_SOURCE_REGISTRY: dict[str, dict] = {}


def _source_registry() -> dict[str, dict]:
    if not _SOURCE_REGISTRY:
        try:
            from ingestor.sources_catalog import ALL_SOURCES
            for src in ALL_SOURCES:
                _SOURCE_REGISTRY[src["slug"]] = src
        except ImportError:
            pass
    return _SOURCE_REGISTRY


def _author(sense) -> str:
    """Return a citable author string for the source slug, falling back to the slug."""
    src = _source_registry().get(sense.source_slug or "", {})
    return src.get("author") or src.get("short_name") or sense.source_slug or "Unknown"


def _year(sense) -> str:
    return str(sense.first_attested_year) if sense.first_attested_year else "n.d."


def _citation_key(sense) -> str:
    slug = re.sub(r"[^a-z0-9]", "_", (sense.source_slug or "unknown").lower())
    return f"living_lexicon_{sense.word}_{slug}_{_year(sense)}"


def _grade_label(sense) -> str:
    return f"Grade {sense.evidence_grade}" if sense.evidence_grade else ""


def _era_label(sense) -> str:
    return sense.era_name or "undated"


def _definition_excerpt(sense, max_chars: int = 120) -> str:
    defn = sense.definition or ""
    return defn[:max_chars] + ("…" if len(defn) > max_chars else "")


# ---------------------------------------------------------------------------
# BibTeX
# ---------------------------------------------------------------------------

def to_bibtex(sense, access_url: str | None = None) -> str:
    """Return a @misc BibTeX entry for the sense."""
    key = _citation_key(sense)
    author = _author(sense)
    year = _year(sense)
    grade = _grade_label(sense)
    era = _era_label(sense)
    defn = _definition_excerpt(sense)
    url_line = f"  url          = {{{access_url}}},\n" if access_url else ""
    note_parts = [p for p in [f"Source: {sense.source_slug}", defn, grade] if p]

    return (
        f"@misc{{{key},\n"
        f"  title        = {{{{{sense.word}}} [{era} sense{', ' + grade if grade else ''}]}},\n"
        f"  author       = {{{author}}},\n"
        f"  howpublished = {{Living Lexicon semantic database}},\n"
        f"  year         = {{{year}}},\n"
        f"  note         = {{{'. '.join(note_parts)}}},\n"
        f"{url_line}"
        f"}}"
    )


# ---------------------------------------------------------------------------
# APA 7th edition
# ---------------------------------------------------------------------------

def to_apa(sense, access_url: str | None = None) -> str:
    """Return an APA 7th edition citation string."""
    author = _author(sense)
    year = _year(sense)
    era = _era_label(sense)
    grade = _grade_label(sense)
    qualifier = f"{era} sense" + (f", {grade}" if grade else "")
    url_part = f" {access_url}" if access_url else ""
    return (
        f"{author}. ({year}). \"{sense.word}\" [{qualifier}]. "
        f"In *Living Lexicon* (semantic database).{url_part}"
    )


# ---------------------------------------------------------------------------
# MLA 9th edition
# ---------------------------------------------------------------------------

def to_mla(sense, access_url: str | None = None) -> str:
    """Return an MLA 9th edition Works Cited entry."""
    author = _author(sense)
    era = _era_label(sense)
    year = _year(sense)
    grade = _grade_label(sense)
    qualifier = era + (f", {grade}" if grade else "")
    url_part = f" {access_url}." if access_url else ""
    return (
        f"\"{sense.word}.\" *Living Lexicon*, sense ID {sense.sense_id}, "
        f"{qualifier}. {author}, {year}.{url_part}"
    )


# ---------------------------------------------------------------------------
# Chicago 17th edition (notes-bibliography)
# ---------------------------------------------------------------------------

def to_chicago(sense, access_url: str | None = None) -> str:
    """Return a Chicago 17th edition bibliography entry."""
    author = _author(sense)
    era = _era_label(sense)
    year = _year(sense)
    grade = _grade_label(sense)
    qualifier = f"{era} sense" + (f", {grade}" if grade else "")
    url_part = f" {access_url}." if access_url else "."
    return (
        f"{author}. \"{sense.word} ({qualifier}).\" "
        f"*Living Lexicon*. Accessed {year}.{url_part}"
    )


# ---------------------------------------------------------------------------
# Multi-sense BibTeX block (for word-level citation)
# ---------------------------------------------------------------------------

def word_to_bibtex(senses: list, access_base_url: str | None = None) -> str:
    """Return a multi-entry BibTeX block, one entry per sense ordered by year."""
    ordered = sorted(senses, key=lambda s: s.first_attested_year or 0)
    entries = []
    for sense in ordered:
        url = f"{access_base_url}/{sense.sense_id}" if access_base_url else None
        entries.append(to_bibtex(sense, access_url=url))
    return "\n\n".join(entries)
