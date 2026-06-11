from __future__ import annotations

import sys
from types import SimpleNamespace

from ingestor.common_words_pg_importer import (
    CommonWordCandidate,
    ingest_common_words,
    load_common_words,
    normalize_candidate,
)


def test_normalize_candidate_skips_invalid_tokens():
    assert normalize_candidate("Invisible") == "invisible"
    assert normalize_candidate("ice cream") == ""
    assert normalize_candidate("word-thing") == ""
    assert normalize_candidate("123") == ""
    assert normalize_candidate("a") == "a"


def test_load_common_words_respects_rank_window_and_filters(monkeypatch):
    fake_wordfreq = SimpleNamespace(
        top_n_list=lambda language, count: [
            "the",
            "of",
            "ice cream",
            "Invisible",
            "word-thing",
            "reason",
        ][:count],
        zipf_frequency=lambda word, language: {
            "the": 7.7,
            "of": 7.4,
            "invisible": 4.2,
            "reason": 5.1,
        }.get(word, 0.0),
    )
    monkeypatch.setitem(sys.modules, "wordfreq", fake_wordfreq)

    records = load_common_words(start_rank=2, limit=5, min_zipf=4.0)

    assert records == [
        CommonWordCandidate(word="of", rank=2, zipf=7.4),
        CommonWordCandidate(word="invisible", rank=4, zipf=4.2),
        CommonWordCandidate(word="reason", rank=6, zipf=5.1),
    ]


def test_ingest_common_words_dry_run_does_not_connect(monkeypatch):
    def fail_connect(*args, **kwargs):
        raise AssertionError("dry run should not connect to PostgreSQL")

    monkeypatch.setattr("ingestor.common_words_pg_importer.psycopg2.connect", fail_connect)
    result = ingest_common_words(
        [CommonWordCandidate(word="invisible", rank=1200, zipf=4.2)],
        dry_run=True,
    )

    assert result.ok
    assert result.dry_run is True
    assert result.ingested == 1


def test_ingest_common_words_existing_row_updates_frequency_without_insert(monkeypatch):
    calls = []

    class Cursor:
        rowcount = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params):
            calls.append((sql, params))
            self.rowcount = 1

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return Cursor()

        def close(self):
            pass

    monkeypatch.setattr("ingestor.common_words_pg_importer.psycopg2.connect", lambda *args: Connection())

    result = ingest_common_words(
        [CommonWordCandidate(word="invisible", rank=1200, zipf=4.2)],
        dry_run=False,
    )

    assert result.ok
    assert result.ingested == 1
    assert len(calls) == 1
    assert "UPDATE words" in calls[0][0]
