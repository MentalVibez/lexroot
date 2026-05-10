from living_lexicon import WordHistorian


class FakeStore:
    def __init__(self, words, claims=None):
        self.words = words
        self.claims = claims or {}

    def get_word(self, word):
        return self.words.get(word.lower())

    def get_word_sources(self, word):
        return []

    def get_etymology_claims(self, word):
        return self.claims.get(word.lower(), [])

    def get_era_timeline(self, word):
        return []


def test_word_detective_identifies_standard_silent_e_rule():
    historian = WordHistorian(
        store=FakeStore({
            "make": {
                "name": "make",
                "language": "English",
                "definition": "To create or form.",
                "root": "macian",
                "root_meaning": "to make",
                "root_origin": "Old English",
                "cognates": [],
            }
        }),
        llm=None,
    )

    result = historian.word_detective("make")

    assert result.classification == "standard_phonics_rule"
    assert result.standard_rules[0]["label"] == "silent-e long vowel"
    assert result.historical_exceptions == []


def test_word_detective_uses_greek_root_for_historical_exception():
    historian = WordHistorian(
        store=FakeStore(
            {
                "phone": {
                    "name": "phone",
                    "language": "English",
                    "definition": "A sound-transmitting device.",
                    "root": "phone",
                    "root_meaning": "voice, sound",
                    "root_origin": "Greek",
                    "cognates": [],
                }
            },
            {
                "phone": [
                    {
                        "id": "phone-greek",
                        "relation_type": "derived_from",
                        "source_form": "phone",
                        "source_language": "Greek",
                        "confidence": "high",
                        "source_tier": 1,
                    }
                ]
            },
        ),
        llm=None,
    )

    result = historian.word_detective("phone")

    assert result.classification == "historical_exception"
    assert result.historical_exceptions[0]["label"] == "Greek ph"
    assert result.root_clue["origin_language"] == "Greek"


def test_word_detective_uses_germanic_root_for_silent_letter_history():
    historian = WordHistorian(
        store=FakeStore({
            "knee": {
                "name": "knee",
                "language": "English",
                "definition": "The joint between thigh and lower leg.",
                "root": "cneo",
                "root_meaning": "knee",
                "root_origin": "Old English",
                "cognates": [],
            }
        }),
        llm=None,
    )

    result = historian.word_detective("knee")

    assert result.classification == "historical_exception"
    assert result.historical_exceptions[0]["label"] == "silent k"


def test_word_detective_can_use_curated_spelling_history(tmp_path, monkeypatch):
    from living_lexicon import word_detective

    path = tmp_path / "spelling_history.csv"
    path.write_text(
        "word,phonics_rule_applies,standard_phonics_rule,spelling_history_type,exception_reason,"
        "spelling_explanation,root_influence,evidence_grade,confidence_reason\n"
        "debt,false,,latin_learned_spelling,Restored b from Latin debitum,"
        "The spelling keeps a learned Latin b that is not pronounced.,Latin debitum,C,"
        "Specialist etymological source supports the learned spelling.\n",
        encoding="utf-8",
    )
    word_detective.load_spelling_history.cache_clear()
    monkeypatch.setattr(word_detective, "DEFAULT_SPELLING_HISTORY", path)
    monkeypatch.setattr(word_detective, "load_spelling_history", word_detective.lru_cache(maxsize=1)(lambda p=str(path): {
        "debt": {
            "word": "debt",
            "phonics_rule_applies": "false",
            "spelling_history_type": "latin_learned_spelling",
            "exception_reason": "Restored b from Latin debitum",
            "spelling_explanation": "The spelling keeps a learned Latin b that is not pronounced.",
            "root_influence": "Latin debitum",
            "evidence_grade": "C",
            "confidence_reason": "Specialist etymological source supports the learned spelling.",
        }
    }))

    historian = WordHistorian(
        store=FakeStore({
            "debt": {
                "name": "debt",
                "language": "English",
                "definition": "Something owed.",
                "root": "debitum",
                "root_meaning": "thing owed",
                "root_origin": "Latin",
                "cognates": [],
            }
        }),
        llm=None,
    )

    result = historian.word_detective("debt")

    assert result.classification == "historical_exception"
    assert result.spelling_history_type == "latin_learned_spelling"
    assert result.phonics_rule_applies is False
    assert result.evidence_grade == "C"
