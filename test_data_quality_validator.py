import csv
import json

from ingestor.data_quality_validator import validate


FIELDS = [
    "entry",
    "entry_type",
    "definition",
    "confidence",
    "source_agent",
    "evidence_grade",
    "confidence_reason",
    "citation",
    "origin_theory_status",
    "earliest_known_use_year",
    "literal_meaning",
    "figurative_meaning",
    "semantic_drift_history",
]


def write_rows(path, rows):
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_validator_flags_idiom_quality_requirements(tmp_path):
    path = tmp_path / "lexicon.csv"
    write_rows(path, [
        {
            "entry": "kick the bucket",
            "entry_type": "idiom",
            "definition": "To die.",
            "confidence": "low",
            "source_agent": "curated-idioms",
            "evidence_grade": "",
            "confidence_reason": "",
            "citation": "",
            "origin_theory_status": "",
            "earliest_known_use_year": "",
            "literal_meaning": "",
            "figurative_meaning": "To die.",
            "semantic_drift_history": "",
        }
    ])

    report = validate(path)

    assert report["grade"] == "usable with review queue"
    assert report["issues"]["idiom_low_confidence"] == 1
    assert report["issues"]["idiom_missing_literal_meaning"] == 1


def test_validator_flags_era_record_without_source_or_dates(tmp_path):
    path = tmp_path / "lexicon.csv"
    write_rows(path, [
        {
            "entry": "prevent",
            "entry_type": "word",
            "definition": "To stop something from happening.",
            "confidence": "high",
            "source_agent": "seed_database",
            "evidence_grade": "",
            "confidence_reason": "",
            "citation": "",
            "origin_theory_status": "",
            "earliest_known_use_year": "",
            "literal_meaning": "",
            "figurative_meaning": "",
            "semantic_drift_history": json.dumps([
                {
                    "era_name": "Early Modern English",
                    "meaning": "To come before.",
                    "confidence": "high",
                }
            ]),
        }
    ])

    report = validate(path)

    assert report["issues"]["era_missing_source"] == 1
    assert report["issues"]["era_missing_date_range"] == 1
    assert report["issues"]["era_high_confidence_without_source"] == 1


def test_validator_flags_high_confidence_without_strong_evidence(tmp_path):
    path = tmp_path / "lexicon.csv"
    write_rows(path, [
        {
            "entry": "nice",
            "entry_type": "word",
            "definition": "Pleasant.",
            "confidence": "high",
            "source_agent": "seed_database",
            "evidence_grade": "D",
            "confidence_reason": "",
            "citation": "",
            "origin_theory_status": "",
            "earliest_known_use_year": "",
            "literal_meaning": "",
            "figurative_meaning": "",
            "semantic_drift_history": "",
        }
    ])

    report = validate(path, senses_path=tmp_path / "missing.csv", attestations_path=tmp_path / "missing2.csv")

    assert report["grade"] == "needs fixes"
    assert report["issues"]["high_confidence_without_sufficient_evidence"] == 1
    assert report["issues"]["missing_confidence_reason"] == 1


def test_validator_flags_inferred_sense_and_missing_attestation(tmp_path):
    lexicon = tmp_path / "lexicon.csv"
    write_rows(lexicon, [])
    senses = tmp_path / "senses.csv"
    with senses.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "sense_id",
                "word",
                "definition",
                "meaning_type",
                "first_attested_year",
                "source_slug",
                "confidence",
                "evidence_grade",
            ],
        )
        writer.writeheader()
        writer.writerow({
            "sense_id": "root-only",
            "word": "example",
            "definition": "Inferred root meaning.",
            "meaning_type": "inferred_from_etymology",
            "first_attested_year": "1400",
            "source_slug": "",
            "confidence": "high",
            "evidence_grade": "C",
        })

    report = validate(lexicon, senses_path=senses, attestations_path=tmp_path / "att.csv")

    assert report["issues"]["sense_without_attestation"] == 1
    assert report["issues"]["first_attested_without_source"] == 1
    assert report["issues"]["etymology_inference_wrong_evidence_grade"] == 1
    assert report["issues"]["etymology_inference_high_confidence"] == 1


def test_validator_flags_uncertain_idiom_origin_high_confidence(tmp_path):
    path = tmp_path / "lexicon.csv"
    write_rows(path, [
        {
            "entry": "spill the beans",
            "entry_type": "idiom",
            "definition": "To reveal a secret.",
            "confidence": "high",
            "source_agent": "curated-idioms",
            "evidence_grade": "B",
            "confidence_reason": "Has a citation, but the origin story is folklore.",
            "citation": "Example citation",
            "origin_theory_status": "folk_etymology",
            "earliest_known_use_year": "1900",
            "literal_meaning": "To spill beans.",
            "figurative_meaning": "To reveal a secret.",
            "semantic_drift_history": "",
        }
    ])

    report = validate(path, senses_path=tmp_path / "missing.csv", attestations_path=tmp_path / "missing2.csv")

    assert report["issues"]["idiom_uncertain_origin_high_confidence"] == 1


def test_validator_flags_spelling_exception_without_reason(tmp_path):
    lexicon = tmp_path / "lexicon.csv"
    write_rows(lexicon, [])
    spelling = tmp_path / "spelling_history.csv"
    with spelling.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "word",
                "spelling_history_type",
                "exception_reason",
                "evidence_grade",
                "confidence_reason",
            ],
        )
        writer.writeheader()
        writer.writerow({
            "word": "debt",
            "spelling_history_type": "latin_learned_spelling",
            "exception_reason": "",
            "evidence_grade": "C",
            "confidence_reason": "",
        })

    report = validate(
        lexicon,
        senses_path=tmp_path / "missing.csv",
        attestations_path=tmp_path / "missing2.csv",
        spelling_history_path=spelling,
    )

    assert report["issues"]["spelling_exception_without_explanation"] == 1
    assert report["issues"]["missing_confidence_reason"] == 1
