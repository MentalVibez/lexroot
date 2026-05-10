"""Deterministic spelling-history clues for Word Detective."""
from __future__ import annotations

from dataclasses import dataclass
import csv
from functools import lru_cache
from pathlib import Path
import re

from living_lexicon.models import EtymologyClaimInfo, RootInfo


@dataclass(frozen=True)
class SpellingRule:
    pattern: str
    label: str
    explanation: str
    root_families: tuple[str, ...] = ()
    historical: bool = False


WORDS_DIR = Path(__file__).parent.parent / "Words"
DEFAULT_SPELLING_HISTORY = WORDS_DIR / "sources" / "spelling_history.csv"


STANDARD_RULES: tuple[SpellingRule, ...] = (
    SpellingRule(
        pattern=r"[aeiou][bcdfghjklmnpqrstvwxyz]e$",
        label="silent-e long vowel",
        explanation="Final silent e commonly marks the previous vowel as long.",
    ),
    SpellingRule(
        pattern=r"c(?=[eiy])",
        label="soft c",
        explanation="C before e, i, or y commonly says /s/ in English.",
    ),
    SpellingRule(
        pattern=r"g(?=[eiy])",
        label="soft g",
        explanation="G before e, i, or y often says /j/ in English.",
    ),
    SpellingRule(
        pattern=r"ck($|[a-z])",
        label="ck after short vowel",
        explanation="CK commonly spells /k/ after a short vowel.",
    ),
    SpellingRule(
        pattern=r"[^aeiou]y$",
        label="final y vowel",
        explanation="Final y often acts as a vowel sound.",
    ),
    SpellingRule(
        pattern=r"(sh|ch|th|wh)",
        label="common consonant digraph",
        explanation="This spelling uses a common English consonant team.",
    ),
)


HISTORICAL_RULES: tuple[SpellingRule, ...] = (
    SpellingRule(
        pattern=r"^kn",
        label="silent k",
        explanation="Initial kn keeps an older Germanic consonant cluster that later lost the /k/ sound.",
        root_families=("old english", "middle english", "germanic", "old norse"),
        historical=True,
    ),
    SpellingRule(
        pattern=r"^gn",
        label="silent g",
        explanation="Initial gn often preserves an older cluster whose first sound disappeared in modern speech.",
        root_families=("old english", "middle english", "germanic", "greek", "latin"),
        historical=True,
    ),
    SpellingRule(
        pattern=r"^wr",
        label="silent w",
        explanation="Initial wr preserves an older English/Germanic spelling where w was once pronounced.",
        root_families=("old english", "middle english", "germanic"),
        historical=True,
    ),
    SpellingRule(
        pattern=r"gh",
        label="historical gh",
        explanation="GH often marks an older sound that weakened, vanished, or shifted after Middle English.",
        root_families=("old english", "middle english", "germanic"),
        historical=True,
    ),
    SpellingRule(
        pattern=r"^ps|^pn|^pt|^rh",
        label="Greek initial cluster",
        explanation="This keeps a Greek-derived initial cluster that English often simplifies in speech.",
        root_families=("greek",),
        historical=True,
    ),
    SpellingRule(
        pattern=r"ph",
        label="Greek ph",
        explanation="PH commonly preserves Greek phi, now pronounced /f/ in English.",
        root_families=("greek",),
        historical=True,
    ),
    SpellingRule(
        pattern=r"ch",
        label="Greek ch",
        explanation="In many Greek-derived words, ch preserves Greek chi and is pronounced /k/ rather than the usual English ch sound.",
        root_families=("greek",),
        historical=True,
    ),
    SpellingRule(
        pattern=r"que$",
        label="French final que",
        explanation="Final que is a French/Latin spelling history for a /k/ sound.",
        root_families=("french", "latin"),
        historical=True,
    ),
    SpellingRule(
        pattern=r"(tion|sion|cious|tious)$",
        label="Latinate suffix spelling",
        explanation="This suffix keeps a Latin/French spelling pattern whose sound has shifted in English.",
        root_families=("latin", "french"),
        historical=True,
    ),
    SpellingRule(
        pattern=r"mb$",
        label="silent final b",
        explanation="Final mb often preserves an older spelling after the /b/ sound disappeared.",
        root_families=("old english", "middle english", "germanic"),
        historical=True,
    ),
    SpellingRule(
        pattern=r"bt",
        label="historical bt",
        explanation="BT in English words is often a historical or learned spelling rather than a transparent sound spelling.",
        root_families=("latin", "french"),
        historical=True,
    ),
)


def normalize_root_family(value: str | None) -> str:
    return (value or "").casefold().replace("-", " ").strip()


def root_matches(rule: SpellingRule, root_families: set[str]) -> bool:
    if not rule.root_families:
        return True
    return any(family in root for family in rule.root_families for root in root_families)


def _clean(value: str | None) -> str:
    return (value or "").strip()


@lru_cache(maxsize=1)
def load_spelling_history(path: str = str(DEFAULT_SPELLING_HISTORY)) -> dict[str, dict[str, str]]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    rows: dict[str, dict[str, str]] = {}
    with file_path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            word = _clean(row.get("word")).casefold()
            if word:
                rows[word] = {key: _clean(value) for key, value in row.items()}
    return rows


def _bool_or_none(value: str | None) -> bool | None:
    cleaned = _clean(value).casefold()
    if cleaned in {"true", "yes", "1"}:
        return True
    if cleaned in {"false", "no", "0"}:
        return False
    return None


def detect_spelling_rules(
    word: str,
    root: RootInfo,
    claims: list[EtymologyClaimInfo],
) -> dict:
    clean_word = re.sub(r"[^a-z]", "", word.casefold())
    curated = load_spelling_history().get(word.casefold()) or load_spelling_history().get(clean_word)
    root_families = {
        normalize_root_family(root.origin_language),
        normalize_root_family(root.name),
    }
    root_families.update(normalize_root_family(claim.source_language) for claim in claims)
    root_families.update(normalize_root_family(claim.source_form) for claim in claims)
    root_families = {family for family in root_families if family}

    historical_matches = [
        rule for rule in HISTORICAL_RULES
        if re.search(rule.pattern, clean_word) and root_matches(rule, root_families)
    ]
    standard_matches = [
        rule for rule in STANDARD_RULES
        if re.search(rule.pattern, clean_word)
    ]

    if historical_matches:
        classification = "historical_exception"
        summary = "This spelling keeps historical root evidence that no longer maps cleanly to modern phonics."
    elif standard_matches:
        classification = "standard_phonics_rule"
        summary = "This spelling follows a common English phonics pattern."
    else:
        classification = "undetermined"
        summary = "No strong standard-rule or root-history spelling clue was found in the current data."

    confidence = 0.45
    if historical_matches:
        confidence = 0.82 if root_families else 0.68
    elif standard_matches:
        confidence = 0.72
    if claims:
        confidence += 0.08

    if curated:
        spelling_history_type = curated.get("spelling_history_type") or None
        if spelling_history_type == "regular_phonics":
            classification = "standard_phonics_rule"
        elif spelling_history_type and spelling_history_type != "unknown":
            classification = "historical_exception"
        summary = curated.get("spelling_explanation") or curated.get("exception_reason") or summary
        confidence = max(confidence, 0.88 if curated.get("evidence_grade") in {"A", "B", "C"} else 0.76)
    else:
        spelling_history_type = (
            "regular_phonics"
            if standard_matches and not historical_matches
            else "unknown"
        )

    return {
        "classification": classification,
        "confidence": round(min(confidence, 0.95), 2),
        "summary": summary,
        "phonics_rule_applies": (
            _bool_or_none(curated.get("phonics_rule_applies")) if curated else bool(standard_matches)
        ),
        "standard_phonics_rule": (
            curated.get("standard_phonics_rule") if curated else (standard_matches[0].label if standard_matches else None)
        ),
        "spelling_history_type": spelling_history_type,
        "exception_reason": curated.get("exception_reason") if curated else None,
        "spelling_explanation": curated.get("spelling_explanation") if curated else summary,
        "root_influence": curated.get("root_influence") if curated else root.name,
        "evidence_grade": curated.get("evidence_grade") if curated else None,
        "confidence_reason": curated.get("confidence_reason") if curated else None,
        "root_clue": {
            "name": root.name,
            "meaning": root.meaning,
            "origin_language": root.origin_language,
            "claim_languages": sorted({
                claim.source_language for claim in claims if claim.source_language
            }),
        },
        "standard_rules": [
            {
                "label": rule.label,
                "explanation": rule.explanation,
            }
            for rule in standard_matches
        ],
        "historical_exceptions": [
            {
                "label": rule.label,
                "explanation": rule.explanation,
                "root_families": list(rule.root_families),
            }
            for rule in historical_matches
        ],
    }
