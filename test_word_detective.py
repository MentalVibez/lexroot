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
