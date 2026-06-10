from ingestor import etymology_db_importer, etymwn_importer


def test_etymwn_prefers_germanic_source_over_latin_when_both_exist(monkeypatch):
    monkeypatch.setattr(etymwn_importer, "_ensure_nltk", lambda: None)
    monkeypatch.setattr(etymwn_importer, "_get_definition", lambda word: "A test definition.")

    entries = etymwn_importer.build_word_entries(
        [
            {
                "eng_word": "house",
                "root_word": "domus",
                "root_origin_language": "Classical Latin",
            },
            {
                "eng_word": "house",
                "root_word": "hus",
                "root_origin_language": "Old English",
            },
        ],
        {},
    )

    assert len(entries) == 1
    assert entries[0].root_name == "hus"
    assert entries[0].root_origin_language == "Old English"


def test_etymology_db_priority_prefers_old_english_over_latin():
    roots = [
        {"root": "domus", "language": "Classical Latin"},
        {"root": "hus", "language": "Old English"},
    ]

    best = min(
        roots,
        key=lambda item: etymology_db_importer.ROOT_SOURCE_PRIORITY.get(item["language"], 99),
    )

    assert best == {"root": "hus", "language": "Old English"}
