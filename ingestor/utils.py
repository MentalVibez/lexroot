"""
Shared utilities for all Living Lexicon importers.

Import instead of copy-pasting:
    from ingestor.utils import clean_str, safe_int, safe_float, WORD_PATTERN, build_arg_parser
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any


# Canonical word validation pattern — used across many importers.
# Matches lowercase English words, hyphenated compounds, and short phrases.
WORD_PATTERN: re.Pattern[str] = re.compile(r"^[a-z][a-z' -]{1,79}$")


def clean_str(value: str | None) -> str:
    """Strip whitespace; return '' for None or empty."""
    return (value or "").strip()


def safe_int(value: Any) -> int | None:
    """
    Convert to int, returning None on failure.

    Handles str, int, float, None, and float-string years like '1300.0'
    that some CSV exporters produce.
    """
    try:
        stripped = clean_str(str(value)) if value is not None else ""
        if not stripped:
            return None
        return int(float(stripped))
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> float | None:
    """Convert to float, returning None on failure."""
    try:
        stripped = clean_str(str(value)) if value is not None else ""
        return float(stripped) if stripped else None
    except (TypeError, ValueError):
        return None


def is_valid_word(word: str, include_phrases: bool = True) -> bool:
    """
    Return True if word matches WORD_PATTERN.

    include_phrases=False rejects multi-word and hyphenated entries,
    useful for importers that only accept single tokens.
    """
    if not word or not WORD_PATTERN.match(word):
        return False
    return include_phrases or (" " not in word and "-" not in word)


def build_arg_parser(
    description: str,
    default_path: str | Path | None = None,
    include_limit: bool = False,
    include_dry_run: bool = True,
    extra_args: list[tuple] | None = None,
) -> argparse.ArgumentParser:
    """
    Build a standard ArgumentParser for importer CLI scripts.

    Standard flags:
    - --path       (if default_path is provided)
    - --dry-run    (if include_dry_run=True)
    - --limit      (if include_limit=True)

    extra_args: list of ([arg_names], {kwargs}) tuples passed to add_argument.
    Example:
        extra_args=[
            (["--source"], {"default": "oed", "help": "Source slug."}),
        ]
    """
    parser = argparse.ArgumentParser(description=description)
    if default_path is not None:
        parser.add_argument(
            "--path",
            default=str(default_path),
            help=f"Input file path. Default: {default_path}",
        )
    if include_dry_run:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and preview without writing to the database.",
        )
    if include_limit:
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Maximum records to process. 0 = no limit.",
        )
    for item in extra_args or []:
        args, kwargs = item
        parser.add_argument(*args, **kwargs)
    return parser
