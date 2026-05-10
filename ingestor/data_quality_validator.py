"""
Validate the clean lexicon import CSV and write a practical quality report.

Usage:
  python3 -m ingestor.data_quality_validator
  python3 -m ingestor.data_quality_validator --path Words/build/lexicon_import.csv
  python3 -m ingestor.data_quality_validator --format json --output Words/build/data_quality_report.json
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
import re
from pathlib import Path
from typing import Any


WORDS_DIR = Path(__file__).parent.parent / "Words"
DEFAULT_INPUT = WORDS_DIR / "build" / "lexicon_import.csv"
DEFAULT_OUTPUT = WORDS_DIR / "build" / "data_quality_report.md"
DEFAULT_SENSES = WORDS_DIR / "sources" / "senses.csv"
DEFAULT_ATTESTATIONS = WORDS_DIR / "sources" / "attestations.csv"
DEFAULT_SPELLING_HISTORY = WORDS_DIR / "sources" / "spelling_history.csv"

VALID_ENTRY_TYPES = {
    "word",
    "idiom",
    "medical_term",
    "phrase",
    "acronym",
    "proper_noun",
}
VALID_CONFIDENCE = {"", "low", "medium", "high"}
VALID_ERA_CONFIDENCE = {"low", "medium", "high", None, ""}
VALID_EVIDENCE_GRADES = {"", "A", "B", "C", "D", "E"}
VALID_SEMANTIC_CHANGE_TYPES = {
    "",
    "broadening",
    "narrowing",
    "amelioration",
    "pejoration",
    "metaphor",
    "metonymy",
    "bleaching",
    "specialization",
    "euphemism",
    "folk_etymology",
    "reanalysis",
    "unknown",
}
VALID_ORIGIN_THEORY_STATUS = {
    "",
    "attested",
    "plausible",
    "disputed",
    "folk_etymology",
    "unknown",
}
VALID_SPELLING_HISTORY_TYPES = {
    "",
    "regular_phonics",
    "latin_learned_spelling",
    "greek_learned_spelling",
    "french_borrowing",
    "old_english_survival",
    "great_vowel_shift",
    "silent_letter_restoration",
    "scribal_convention",
    "analogy",
    "foreign_borrowing",
    "unknown",
}
LOCAL_SOURCE_SLUGS = {
    "",
    "open_definitions",
    "gcide",
    "oewn-2024",
    "kaikki-en",
    "medical_terms",
    "medical_inferred",
    "seed_database",
    "etymwn",
    "collins_hint",
    "wiktionary",
    "curated-idioms",
}

MEDICAL_HINTS = re.compile(
    r"\b("
    r"ablation|acarbose|acromegaly|acupuncture|adenectomy|adenoidectomy|"
    r"adrenalectomy|agranulocytosis|allograft|amniocentesis|amniotomy|"
    r"anaemia|anemia|angioma|angioplasty|appendectomy|aromatherapy|"
    r"arteriotomy|arthrodesis|carcinoma|clinical|diabetes|diagnos(?:is|tic)|"
    r"disorder|fracture|humerus|injury|lesion|malignant|neoplasm|pregnancy|"
    r"pharmaceutical|syndrome|surgical|therapy"
    r")\b",
    flags=re.I,
)


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _parse_drift(raw: str) -> tuple[list[dict[str, Any]], str | None]:
    raw = _clean(raw)
    if not raw:
        return [], None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [], f"invalid JSON: {exc.msg}"
    if isinstance(value, dict):
        return [value], None
    if isinstance(value, list):
        bad = next((item for item in value if not isinstance(item, dict)), None)
        if bad is not None:
            return [], "semantic_drift_history must contain objects"
        return value, None
    return [], "semantic_drift_history must be an object or list"


def _sample_append(samples: dict[str, list[str]], key: str, value: str, limit: int) -> None:
    if len(samples[key]) < limit:
        samples[key].append(value)


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _known_source_slugs() -> set[str]:
    try:
        from ingestor.sources_catalog import ALL_SOURCES

        return LOCAL_SOURCE_SLUGS | {str(source.get("slug", "")).strip() for source in ALL_SOURCES}
    except Exception:
        return set(LOCAL_SOURCE_SLUGS)


def _evidence_grade(row: dict[str, Any]) -> str:
    return _clean(str(row.get("evidence_grade") or "")).upper()


def _has_precise_citation(row: dict[str, Any]) -> bool:
    return any(
        _clean(str(row.get(field) or ""))
        for field in ("citation", "page", "entry_headword", "source_url", "first_attested_source")
    )


def _strong_evidence_for_high_confidence(row: dict[str, Any]) -> bool:
    grade = _evidence_grade(row)
    if grade in {"A", "B"}:
        return bool(_clean(str(row.get("source_slug") or row.get("source_agent") or ""))) and _has_precise_citation(row)
    if grade == "C":
        return bool(_clean(str(row.get("source_slug") or row.get("source_agent") or ""))) and _has_precise_citation(row)
    return False


def _check_source_slug(
    slug: str,
    label: str,
    counters: Counter[str],
    samples: dict[str, list[str]],
    sample_limit: int,
    known_sources: set[str],
) -> None:
    if slug and slug not in known_sources:
        counters["source_slug_not_in_catalog"] += 1
        _sample_append(samples, "source_slug_not_in_catalog", f"{label} source={slug!r}", sample_limit)


def _validate_senses_and_attestations(
    senses_path: Path,
    attestations_path: Path,
    counters: Counter[str],
    samples: dict[str, list[str]],
    sample_limit: int,
    known_sources: set[str],
) -> tuple[int, int]:
    attested_sense_ids: set[str] = set()
    attestation_total = 0
    if attestations_path.exists():
        with attestations_path.open("r", encoding="utf-8", newline="") as fh:
            for row_number, row in enumerate(csv.DictReader(fh), start=2):
                sense_id = _clean(row.get("sense_id"))
                if not sense_id:
                    continue
                attestation_total += 1
                attested_sense_ids.add(sense_id)
                label = f"{attestations_path.name} row {row_number}: {sense_id}"
                grade = _evidence_grade(row)
                source_slug = _clean(row.get("source_slug"))
                _check_source_slug(source_slug, label, counters, samples, sample_limit, known_sources)
                if grade not in VALID_EVIDENCE_GRADES:
                    counters["invalid_evidence_grade"] += 1
                    _sample_append(samples, "invalid_evidence_grade", f"{label} evidence_grade={grade!r}", sample_limit)
                if grade in {"A", "B", "C"} and not _has_precise_citation(row):
                    counters["evidence_missing_precise_citation"] += 1
                    _sample_append(samples, "evidence_missing_precise_citation", label, sample_limit)

    sense_total = 0
    if senses_path.exists():
        with senses_path.open("r", encoding="utf-8", newline="") as fh:
            for row_number, row in enumerate(csv.DictReader(fh), start=2):
                sense_id = _clean(row.get("sense_id"))
                if not sense_id:
                    continue
                sense_total += 1
                label = f"{senses_path.name} row {row_number}: {sense_id}"
                confidence = _clean(row.get("confidence")).casefold()
                meaning_type = _clean(row.get("meaning_type")).casefold()
                grade = _evidence_grade(row)
                semantic_change_type = _clean(row.get("semantic_change_type")).casefold()
                source_slug = _clean(row.get("source_slug"))
                _check_source_slug(source_slug, label, counters, samples, sample_limit, known_sources)

                if sense_id not in attested_sense_ids:
                    counters["sense_without_attestation"] += 1
                    _sample_append(samples, "sense_without_attestation", label, sample_limit)
                if grade not in VALID_EVIDENCE_GRADES:
                    counters["invalid_evidence_grade"] += 1
                    _sample_append(samples, "invalid_evidence_grade", f"{label} evidence_grade={grade!r}", sample_limit)
                if semantic_change_type not in VALID_SEMANTIC_CHANGE_TYPES:
                    counters["invalid_semantic_change_type"] += 1
                    _sample_append(samples, "invalid_semantic_change_type", f"{label} type={semantic_change_type!r}", sample_limit)
                if _safe_int(row.get("first_attested_year")) is not None and not (source_slug or _has_precise_citation(row)):
                    counters["first_attested_without_source"] += 1
                    _sample_append(samples, "first_attested_without_source", label, sample_limit)
                if meaning_type == "inferred_from_etymology":
                    counters["sense_inferred_from_etymology"] += 1
                    if grade != "E":
                        counters["etymology_inference_wrong_evidence_grade"] += 1
                        _sample_append(samples, "etymology_inference_wrong_evidence_grade", label, sample_limit)
                    if confidence == "high":
                        counters["etymology_inference_high_confidence"] += 1
                        _sample_append(samples, "etymology_inference_high_confidence", label, sample_limit)
                if confidence == "high" and not _strong_evidence_for_high_confidence(row):
                    counters["high_confidence_without_sufficient_evidence"] += 1
                    _sample_append(samples, "high_confidence_without_sufficient_evidence", label, sample_limit)
                if confidence == "high" and not _clean(row.get("confidence_reason")):
                    counters["missing_confidence_reason"] += 1
                    _sample_append(samples, "missing_confidence_reason", label, sample_limit)
    return sense_total, attestation_total


def _validate_spelling_history(
    spelling_path: Path,
    counters: Counter[str],
    samples: dict[str, list[str]],
    sample_limit: int,
    known_sources: set[str],
) -> int:
    if not spelling_path.exists():
        return 0
    total = 0
    with spelling_path.open("r", encoding="utf-8", newline="") as fh:
        for row_number, row in enumerate(csv.DictReader(fh), start=2):
            word = _clean(row.get("word"))
            if not word:
                continue
            total += 1
            label = f"{spelling_path.name} row {row_number}: {word}"
            grade = _evidence_grade(row)
            spelling_history_type = _clean(row.get("spelling_history_type")).casefold()
            source_slug = _clean(row.get("source_slug"))
            exception_reason = _clean(row.get("exception_reason"))
            _check_source_slug(source_slug, label, counters, samples, sample_limit, known_sources)
            if grade not in VALID_EVIDENCE_GRADES:
                counters["invalid_evidence_grade"] += 1
                _sample_append(samples, "invalid_evidence_grade", f"{label} evidence_grade={grade!r}", sample_limit)
            if spelling_history_type not in VALID_SPELLING_HISTORY_TYPES:
                counters["invalid_spelling_history_type"] += 1
                _sample_append(samples, "invalid_spelling_history_type", f"{label} type={spelling_history_type!r}", sample_limit)
            if spelling_history_type and spelling_history_type != "regular_phonics" and not exception_reason:
                counters["spelling_exception_without_explanation"] += 1
                _sample_append(samples, "spelling_exception_without_explanation", label, sample_limit)
            if grade in {"A", "B", "C"} and not _has_precise_citation(row):
                counters["evidence_missing_precise_citation"] += 1
                _sample_append(samples, "evidence_missing_precise_citation", label, sample_limit)
            if grade and not _clean(row.get("confidence_reason")):
                counters["missing_confidence_reason"] += 1
                _sample_append(samples, "missing_confidence_reason", label, sample_limit)
    return total


def validate(
    path: Path,
    sample_limit: int = 12,
    senses_path: Path = DEFAULT_SENSES,
    attestations_path: Path = DEFAULT_ATTESTATIONS,
    spelling_history_path: Path = DEFAULT_SPELLING_HISTORY,
) -> dict[str, Any]:
    counters: Counter[str] = Counter()
    entry_types: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    definition_source_counts: Counter[str] = Counter()
    samples: dict[str, list[str]] = defaultdict(list)
    seen_casefold: dict[str, str] = {}
    era_total = 0
    known_sources = _known_source_slugs()

    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        required = {"entry", "entry_type", "definition", "semantic_drift_history"}
        missing_columns = sorted(required - set(fieldnames))
        if missing_columns:
            return {
                "path": str(path),
                "fatal": f"Missing required columns: {', '.join(missing_columns)}",
            }

        for row_number, row in enumerate(reader, start=2):
            counters["total_rows"] += 1
            entry = _clean(row.get("entry"))
            entry_type = _clean(row.get("entry_type")).casefold() or "word"
            definition = _clean(row.get("definition"))
            confidence = _clean(row.get("confidence")).casefold()
            evidence_grade = _evidence_grade(row)
            source = _clean(row.get("source_agent"))
            definition_source = _clean(row.get("definition_source_slug"))
            origin_theory_status = _clean(row.get("origin_theory_status")).casefold()
            source_counts[source or "(none)"] += 1
            definition_source_counts[definition_source or "(none)"] += 1
            confidence_counts[confidence or "(none)"] += 1
            entry_types[entry_type] += 1

            label = f"row {row_number}: {entry or '(blank)'}"

            if not entry:
                counters["blank_entry"] += 1
                _sample_append(samples, "blank_entry", label, sample_limit)
                continue

            folded = entry.casefold()
            if folded in seen_casefold and seen_casefold[folded] != entry:
                counters["duplicate_case_variant"] += 1
                _sample_append(
                    samples,
                    "duplicate_case_variant",
                    f"{label} duplicates casing of {seen_casefold[folded]!r}",
                    sample_limit,
                )
            else:
                seen_casefold[folded] = entry

            if entry_type not in VALID_ENTRY_TYPES:
                counters["unknown_entry_type"] += 1
                _sample_append(samples, "unknown_entry_type", f"{label} type={entry_type!r}", sample_limit)

            if confidence not in VALID_CONFIDENCE:
                counters["invalid_confidence"] += 1
                _sample_append(samples, "invalid_confidence", f"{label} confidence={confidence!r}", sample_limit)

            if evidence_grade not in VALID_EVIDENCE_GRADES:
                counters["invalid_evidence_grade"] += 1
                _sample_append(samples, "invalid_evidence_grade", f"{label} evidence_grade={evidence_grade!r}", sample_limit)

            _check_source_slug(source, label, counters, samples, sample_limit, known_sources)
            _check_source_slug(definition_source, label, counters, samples, sample_limit, known_sources)

            if not definition:
                counters["missing_definition"] += 1
                _sample_append(samples, "missing_definition", label, sample_limit)

            if confidence == "high" and not source:
                counters["high_confidence_without_source"] += 1
                _sample_append(samples, "high_confidence_without_source", label, sample_limit)
            if confidence == "high" and evidence_grade and not _strong_evidence_for_high_confidence(row):
                counters["high_confidence_without_sufficient_evidence"] += 1
                _sample_append(samples, "high_confidence_without_sufficient_evidence", label, sample_limit)
            if confidence == "high" and evidence_grade and not _clean(row.get("confidence_reason")):
                counters["missing_confidence_reason"] += 1
                _sample_append(samples, "missing_confidence_reason", label, sample_limit)

            if entry_type == "idiom":
                if not _clean(row.get("figurative_meaning")):
                    counters["idiom_missing_figurative_meaning"] += 1
                    _sample_append(samples, "idiom_missing_figurative_meaning", label, sample_limit)
                if not _clean(row.get("literal_meaning")):
                    counters["idiom_missing_literal_meaning"] += 1
                    _sample_append(samples, "idiom_missing_literal_meaning", label, sample_limit)
                if confidence in {"", "low"}:
                    counters["idiom_low_confidence"] += 1
                    _sample_append(samples, "idiom_low_confidence", label, sample_limit)
                if origin_theory_status not in VALID_ORIGIN_THEORY_STATUS:
                    counters["idiom_invalid_origin_theory_status"] += 1
                    _sample_append(samples, "idiom_invalid_origin_theory_status", f"{label} status={origin_theory_status!r}", sample_limit)
                if not _clean(row.get("earliest_known_use_year")):
                    counters["idiom_missing_earliest_known_use_year"] += 1
                    _sample_append(samples, "idiom_missing_earliest_known_use_year", label, sample_limit)
                if origin_theory_status in {"disputed", "folk_etymology", "unknown"} and confidence == "high":
                    counters["idiom_uncertain_origin_high_confidence"] += 1
                    _sample_append(samples, "idiom_uncertain_origin_high_confidence", label, sample_limit)

            if entry_type == "word" and (MEDICAL_HINTS.search(entry) or MEDICAL_HINTS.search(definition)):
                counters["likely_medical_term_typed_word"] += 1
                _sample_append(samples, "likely_medical_term_typed_word", label, sample_limit)

            drift, drift_error = _parse_drift(_clean(row.get("semantic_drift_history")))
            if drift_error:
                counters["invalid_semantic_drift_history"] += 1
                _sample_append(samples, "invalid_semantic_drift_history", f"{label}: {drift_error}", sample_limit)
                continue

            for era in drift:
                era_total += 1
                era_name = _clean(str(era.get("era_name") or ""))
                meaning = _clean(str(era.get("meaning") or ""))
                source_slug = _clean(str(era.get("source_slug") or ""))
                era_confidence = _clean(str(era.get("confidence") or "")).casefold()
                era_evidence_grade = _clean(str(era.get("evidence_grade") or "")).upper()
                start_year = _safe_int(era.get("start_year"))
                end_year = _safe_int(era.get("end_year"))

                if not era_name:
                    counters["era_missing_name"] += 1
                    _sample_append(samples, "era_missing_name", label, sample_limit)
                if not meaning:
                    counters["era_missing_meaning"] += 1
                    _sample_append(samples, "era_missing_meaning", f"{label} era={era_name or '(blank)'}", sample_limit)
                if not source_slug:
                    counters["era_missing_source"] += 1
                    _sample_append(samples, "era_missing_source", f"{label} era={era_name or '(blank)'}", sample_limit)
                if start_year is None or end_year is None:
                    counters["era_missing_date_range"] += 1
                    _sample_append(samples, "era_missing_date_range", f"{label} era={era_name or '(blank)'}", sample_limit)
                elif start_year > end_year:
                    counters["era_invalid_date_range"] += 1
                    _sample_append(samples, "era_invalid_date_range", f"{label} {start_year}>{end_year}", sample_limit)
                if era_confidence not in VALID_ERA_CONFIDENCE:
                    counters["era_invalid_confidence"] += 1
                    _sample_append(samples, "era_invalid_confidence", f"{label} confidence={era_confidence!r}", sample_limit)
                if era_confidence == "high" and not source_slug:
                    counters["era_high_confidence_without_source"] += 1
                    _sample_append(samples, "era_high_confidence_without_source", label, sample_limit)
                if era_evidence_grade not in VALID_EVIDENCE_GRADES:
                    counters["invalid_evidence_grade"] += 1
                    _sample_append(samples, "invalid_evidence_grade", f"{label} era={era_name or '(blank)'} grade={era_evidence_grade!r}", sample_limit)
                if era_confidence == "high" and era_evidence_grade and era_evidence_grade not in {"A", "B", "C"}:
                    counters["high_confidence_without_sufficient_evidence"] += 1
                    _sample_append(samples, "high_confidence_without_sufficient_evidence", f"{label} era={era_name or '(blank)'}", sample_limit)

    sense_total, attestation_total = _validate_senses_and_attestations(
        Path(senses_path),
        Path(attestations_path),
        counters,
        samples,
        sample_limit,
        known_sources,
    )
    spelling_history_total = _validate_spelling_history(
        Path(spelling_history_path),
        counters,
        samples,
        sample_limit,
        known_sources,
    )

    serious = (
        counters["blank_entry"]
        + counters["unknown_entry_type"]
        + counters["invalid_confidence"]
        + counters["invalid_semantic_drift_history"]
        + counters["era_invalid_date_range"]
        + counters["era_high_confidence_without_source"]
        + counters["high_confidence_without_source"]
        + counters["high_confidence_without_sufficient_evidence"]
        + counters["etymology_inference_high_confidence"]
        + counters["etymology_inference_wrong_evidence_grade"]
        + counters["idiom_uncertain_origin_high_confidence"]
        + counters["invalid_evidence_grade"]
    )
    review = (
        counters["missing_definition"]
        + counters["likely_medical_term_typed_word"]
        + counters["era_missing_source"]
        + counters["era_missing_date_range"]
        + counters["idiom_low_confidence"]
        + counters["sense_without_attestation"]
        + counters["first_attested_without_source"]
        + counters["spelling_exception_without_explanation"]
        + counters["missing_confidence_reason"]
        + counters["source_slug_not_in_catalog"]
        + counters["evidence_missing_precise_citation"]
        + counters["idiom_missing_earliest_known_use_year"]
    )

    if serious:
        grade = "needs fixes"
    elif review:
        grade = "usable with review queue"
    else:
        grade = "clean"

    return {
        "path": str(path),
        "grade": grade,
        "total_rows": counters["total_rows"],
        "total_era_records": era_total,
        "total_senses": sense_total,
        "total_attestations": attestation_total,
        "total_spelling_history_records": spelling_history_total,
        "entry_types": dict(entry_types.most_common()),
        "confidence": dict(confidence_counts.most_common()),
        "top_sources": dict(source_counts.most_common(12)),
        "definition_sources": dict(definition_source_counts.most_common(12)),
        "issues": dict(counters),
        "samples": dict(samples),
    }


def _issue_table(report: dict[str, Any]) -> str:
    issues = report.get("issues", {})
    rows = []
    for key, count in sorted(issues.items()):
        if key == "total_rows" or not count:
            continue
        rows.append(f"| `{key}` | {count:,} |")
    if not rows:
        return "No issues found.\n"
    return "| Issue | Count |\n|---|---:|\n" + "\n".join(rows) + "\n"


def render_markdown(report: dict[str, Any]) -> str:
    if report.get("fatal"):
        return f"# Data Quality Report\n\nFatal: {report['fatal']}\n"

    lines = [
        "# Data Quality Report",
        "",
        f"Input: `{report['path']}`",
        f"Grade: **{report['grade']}**",
        f"Rows: **{report['total_rows']:,}**",
        f"Era records: **{report['total_era_records']:,}**",
        f"Senses: **{report.get('total_senses', 0):,}**",
        f"Attestations: **{report.get('total_attestations', 0):,}**",
        f"Spelling history records: **{report.get('total_spelling_history_records', 0):,}**",
        "",
        "## Entry Types",
        "",
        "| Type | Count |",
        "|---|---:|",
    ]
    lines.extend(f"| `{key}` | {value:,} |" for key, value in report["entry_types"].items())
    lines.extend(["", "## Confidence", "", "| Confidence | Count |", "|---|---:|"])
    lines.extend(f"| `{key}` | {value:,} |" for key, value in report["confidence"].items())
    lines.extend(["", "## Top Sources", "", "| Source | Count |", "|---|---:|"])
    lines.extend(f"| `{key}` | {value:,} |" for key, value in report["top_sources"].items())
    lines.extend(["", "## Definition Sources", "", "| Source | Count |", "|---|---:|"])
    lines.extend(f"| `{key}` | {value:,} |" for key, value in report["definition_sources"].items())
    lines.extend(["", "## Issues", "", _issue_table(report), "## Samples", ""])

    samples = report.get("samples") or {}
    if not samples:
        lines.append("No samples to show.")
    else:
        for key, values in sorted(samples.items()):
            lines.extend([f"### `{key}`", ""])
            lines.extend(f"- {value}" for value in values)
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Living Lexicon import data quality.")
    parser.add_argument("--path", default=str(DEFAULT_INPUT), help="CSV file to validate.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Report output path.")
    parser.add_argument("--senses", default=str(DEFAULT_SENSES), help="Senses CSV path.")
    parser.add_argument("--attestations", default=str(DEFAULT_ATTESTATIONS), help="Attestations CSV path.")
    parser.add_argument("--spelling-history", default=str(DEFAULT_SPELLING_HISTORY), help="Spelling history CSV path.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--sample-limit", type=int, default=12)
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        raise SystemExit(f"[quality] file not found: {path}")

    report = validate(
        path,
        sample_limit=args.sample_limit,
        senses_path=Path(args.senses),
        attestations_path=Path(args.attestations),
        spelling_history_path=Path(args.spelling_history),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "json":
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        output.write_text(render_markdown(report), encoding="utf-8")

    print(f"[quality] grade={report.get('grade', 'fatal')} rows={report.get('total_rows', 0):,}")
    print(f"[quality] wrote {output}")


if __name__ == "__main__":
    main()
