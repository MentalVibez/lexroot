import csv

from ingestor.shipley_importer import load_shipley_entries


def test_load_shipley_entries_builds_root_claim(tmp_path):
    path = tmp_path / "shipley_roots.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "word",
                "source_form",
                "source_language",
                "root_meaning",
                "relation_type",
                "confidence",
                "page",
                "short_note",
            ],
        )
        writer.writeheader()
        writer.writerow({
            "word": "example",
            "source_form": "*eg-",
            "source_language": "Proto-Indo-European",
            "root_meaning": "to speak",
            "relation_type": "derived_from",
            "confidence": "medium",
            "page": "42",
            "short_note": "test note",
        })

    entries = load_shipley_entries(path)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.name == "example"
    assert entry.root_name == "*eg-"
    assert entry.root_origin_language == "Proto-Indo-European"
    assert entry.etymology_claims[0].source_slug == "shipley-1984"
    assert "Shipley p. 42" in entry.etymology_claims[0].note
