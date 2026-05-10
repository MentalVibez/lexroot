import csv

from ingestor.senses_importer import load_attestations, load_senses


def test_load_senses_normalizes_historical_fields(tmp_path):
    path = tmp_path / "senses.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "sense_id",
                "word",
                "entry_type",
                "part_of_speech",
                "definition",
                "meaning_type",
                "register",
                "domain",
                "era_name",
                "first_attested_year",
                "last_attested_year",
                "first_attested_source",
                "source_slug",
                "confidence",
                "confidence_reason",
                "evidence_grade",
                "citation",
                "page",
                "entry_headword",
                "source_url",
                "access_date",
                "review_status",
                "semantic_change_type",
                "origin_status",
                "usage_region",
                "usage_register",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerow({
            "sense_id": "nice-adj-1300-ignorant",
            "word": "nice",
            "entry_type": "word",
            "part_of_speech": "adjective",
            "definition": "Foolish or ignorant.",
            "meaning_type": "attested",
            "register": "obsolete",
            "domain": "general",
            "era_name": "Middle English",
            "first_attested_year": "1300",
            "last_attested_year": "1500",
            "first_attested_source": "MED nice adj.",
            "source_slug": "oed",
            "confidence": "high",
            "confidence_reason": "Historical dictionary citation with dated sense.",
            "evidence_grade": "B",
            "citation": "OED nice adj. sense 1",
            "page": "",
            "entry_headword": "nice",
            "source_url": "",
            "access_date": "",
            "review_status": "reviewed",
            "semantic_change_type": "pejoration",
            "origin_status": "attested",
            "usage_region": "England",
            "usage_register": "obsolete",
            "notes": "Compact source-backed note.",
        })
        writer.writerow({
            "sense_id": "",
            "word": "skip",
            "definition": "Missing sense id.",
        })

    rows = load_senses(path)

    assert len(rows) == 1
    assert rows[0]["sense_id"] == "nice-adj-1300-ignorant"
    assert rows[0]["first_attested_year"] == 1300
    assert rows[0]["last_attested_year"] == 1500
    assert rows[0]["confidence"] == "high"
    assert rows[0]["evidence_grade"] == "B"
    assert rows[0]["semantic_change_type"] == "pejoration"


def test_load_attestations_keeps_dated_evidence(tmp_path):
    path = tmp_path / "attestations.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "sense_id",
                "word",
                "quote",
                "quote_year",
                "quote_author",
                "quote_work",
                "source_slug",
                "attestation_type",
                "citation",
                "evidence_grade",
                "confidence_reason",
                "page",
                "entry_headword",
                "source_url",
                "access_date",
                "review_status",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerow({
            "sense_id": "nice-adj-1300-ignorant",
            "word": "nice",
            "quote": "A compact fair-use quotation.",
            "quote_year": "1390",
            "quote_author": "Geoffrey Chaucer",
            "quote_work": "Canterbury Tales",
            "source_slug": "middle-english-dictionary",
            "attestation_type": "quotation",
            "citation": "MED nice adj.",
            "evidence_grade": "A",
            "confidence_reason": "Dated quotation evidence.",
            "page": "",
            "entry_headword": "nice",
            "source_url": "",
            "access_date": "",
            "review_status": "reviewed",
            "notes": "Used as dating evidence.",
        })

    rows = load_attestations(path)

    assert len(rows) == 1
    assert rows[0]["quote_year"] == 1390
    assert rows[0]["attestation_type"] == "quotation"
    assert rows[0]["citation"] == "MED nice adj."
    assert rows[0]["evidence_grade"] == "A"
