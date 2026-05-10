"""Etymology path builder — assembles an ordered step-by-step word history.

Pure function module: no DB access, safe to import anywhere.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EtymologyStep:
    form: str
    language: str
    era_or_period: str | None
    meaning: str | None
    reconstruction_level: str = "attested"


@dataclass
class EtymologyPath:
    word: str
    steps: list[EtymologyStep]
    origin_language: str | None
    language_family: str | None
    total_steps: int


def build_etymology_path(
    word_row,
    senses: list,
    relations: list,
) -> EtymologyPath:
    """Assemble an ordered etymology path from oldest known form to the modern word.

    Pulls from three sources, ordered oldest → newest:
    1. Relations of type 'derived_from' (ancestral forms in proto-languages)
    2. word_row.etymology_root + origin_language as the intermediate form
    3. Senses sorted by first_attested_year (recorded historical meanings)
    """
    steps: list[EtymologyStep] = []

    # --- Proto-language ancestors via derived_from relations ---
    ancestor_relations = [
        r for r in (relations or [])
        if getattr(r, "relation_type", "") == "derived_from"
    ]
    for rel in ancestor_relations:
        steps.append(EtymologyStep(
            form=getattr(rel, "to_word", ""),
            language=getattr(rel, "source_slug", "") or "proto-language",
            era_or_period=getattr(rel, "era_name", None),
            meaning=getattr(rel, "notes", None),
            reconstruction_level="reconstructed",
        ))

    # --- Etymology root entry (intermediate ancestor) ---
    root = getattr(word_row, "etymology_root", None)
    origin_lang = getattr(word_row, "origin_language", None)
    if root and root not in {s.form for s in steps}:
        steps.append(EtymologyStep(
            form=root,
            language=origin_lang or "unknown",
            era_or_period=None,
            meaning=None,
            reconstruction_level="attested",
        ))

    # --- Historical senses ordered by first attestation year ---
    sorted_senses = sorted(
        [s for s in (senses or []) if getattr(s, "first_attested_year", None)],
        key=lambda s: s.first_attested_year,
    )
    seen_eras: set[str] = set()
    for s in sorted_senses:
        era = getattr(s, "era_name", None) or str(s.first_attested_year)
        if era in seen_eras:
            continue
        seen_eras.add(era)
        defn = getattr(s, "definition", None)
        steps.append(EtymologyStep(
            form=getattr(word_row, "word", ""),
            language="English",
            era_or_period=era,
            meaning=defn[:100] + "…" if defn and len(defn) > 100 else defn,
            reconstruction_level=getattr(s, "reconstruction_level", None) or "attested",
        ))

    # --- Modern form (always last if we have any historical senses) ---
    if sorted_senses:
        modern_def = getattr(word_row, "definition", None)
        steps.append(EtymologyStep(
            form=getattr(word_row, "word", ""),
            language="Modern English",
            era_or_period="Present",
            meaning=modern_def[:100] + "…" if modern_def and len(modern_def) > 100 else modern_def,
            reconstruction_level="attested",
        ))

    return EtymologyPath(
        word=getattr(word_row, "word", ""),
        steps=steps,
        origin_language=origin_lang,
        language_family=getattr(word_row, "language_family", None),
        total_steps=len(steps),
    )
