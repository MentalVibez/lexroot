"""Vitality Score: V = (0.4 * S) + (0.4 * D) + (0.2 * A)

S — Stability:   evidence quality (authority-weighted) minus semantic change diversity
D — Drift:       change-type breadth + coverage + attested year span
A — Recency:     harmonic decay from last_attested_year to current_year
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache

GRADE_SCORES: dict[str, float] = {"A": 1.0, "B": 0.8, "C": 0.6, "D": 0.4, "E": 0.2}

_TIER_WEIGHTS: dict[int, float] = {1: 1.0, 2: 0.75, 3: 0.50, 4: 0.25}


@lru_cache(maxsize=1)
def _build_slug_tier_map() -> dict[str, float]:
    try:
        from ingestor.sources_catalog import ALL_SOURCES
        return {
            s["slug"]: _TIER_WEIGHTS.get(s.get("authority_tier", 4), 0.25)
            for s in ALL_SOURCES
        }
    except ImportError:
        return {}


def _tier_weight(source_slug: str | None) -> float:
    if not source_slug:
        return 0.5
    return _build_slug_tier_map().get(source_slug, 0.5)

# "unknown" excluded from the denominator — it carries no directional signal
_MEANINGFUL_CHANGE_TYPES = {
    "broadening", "narrowing", "amelioration", "pejoration", "metaphor",
    "metonymy", "bleaching", "specialization", "euphemism", "folk_etymology",
    "reanalysis",
}
_MAX_CHANGE_TYPES = len(_MEANINGFUL_CHANGE_TYPES)

W1, W2, W3 = 0.4, 0.4, 0.2


@dataclass
class VitalityBreakdown:
    vitality_score: float
    stability: float
    drift_velocity: float
    attestation_recency: float
    last_attested_year: int | None
    sense_count: int
    status: str
    frequency_zipf: float | None = None
    authority_weighted: bool = True


def _stability(senses: list) -> float:
    if not senses:
        return 0.5

    weighted_grades = [
        GRADE_SCORES[s.evidence_grade] * _tier_weight(getattr(s, "source_slug", None))
        for s in senses if s.evidence_grade in GRADE_SCORES
    ]
    avg_grade = sum(weighted_grades) / len(weighted_grades) if weighted_grades else 0.5

    distinct_change_types = {
        s.semantic_change_type for s in senses
        if s.semantic_change_type in _MEANINGFUL_CHANGE_TYPES
    }
    change_diversity = len(distinct_change_types) / _MAX_CHANGE_TYPES

    return round(0.6 * avg_grade + 0.4 * (1.0 - change_diversity), 4)


def _drift_velocity(senses: list) -> float:
    if not senses:
        return 0.0

    distinct_change_types = {
        s.semantic_change_type for s in senses
        if s.semantic_change_type in _MEANINGFUL_CHANGE_TYPES
    }
    senses_with_change = sum(
        1 for s in senses if s.semantic_change_type in _MEANINGFUL_CHANGE_TYPES
    )

    all_years = [
        y for s in senses
        for y in (s.first_attested_year, s.last_attested_year)
        if y
    ]
    year_span_norm = min((max(all_years) - min(all_years)) / 1000.0, 1.0) if len(all_years) >= 2 else 0.0

    type_score = len(distinct_change_types) / _MAX_CHANGE_TYPES
    coverage_score = senses_with_change / len(senses)

    return round(0.5 * type_score + 0.3 * coverage_score + 0.2 * year_span_norm, 4)


def _attestation_recency(senses: list, current_year: int) -> float:
    years = [s.last_attested_year for s in senses if s.last_attested_year]
    if not years:
        return 0.5
    gap = current_year - max(years)
    # gap=0 → 1.0 | gap=50 → 0.5 | gap=200 → ~0.2
    return round(1.0 / (1.0 + gap / 50.0), 4)


def _status(vitality: float, drift: float) -> str:
    if vitality >= 0.8:
        return "highly_evolutionary" if drift >= 0.5 else "highly_stable"
    if vitality >= 0.6:
        return "active"
    if vitality >= 0.4:
        return "established"
    if vitality >= 0.2:
        return "declining"
    return "archaic"


def compute_vitality(
    senses: list,
    current_year: int = 2026,
    zipf: float | None = None,
) -> VitalityBreakdown:
    S = _stability(senses)
    D = _drift_velocity(senses)
    A_raw = _attestation_recency(senses, current_year)
    # Blend corpus frequency into recency when available.
    # Zipf 7 = "the" (very common), Zipf 1 = rare hapax → normalise to [0, 1]
    if zipf is not None:
        A = round(0.6 * A_raw + 0.4 * min(zipf / 7.0, 1.0), 4)
    else:
        A = A_raw
    V = round(W1 * S + W2 * D + W3 * A, 4)
    last_attested = max((s.last_attested_year for s in senses if s.last_attested_year), default=None)
    return VitalityBreakdown(
        vitality_score=V,
        stability=S,
        drift_velocity=D,
        attestation_recency=A,
        last_attested_year=last_attested,
        sense_count=len(senses),
        status=_status(V, D),
        frequency_zipf=zipf,
    )
