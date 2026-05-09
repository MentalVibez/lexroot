"""
Shared types and reference data for the etymology agent pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EtymologyRecord:
    word: str
    phonemes: str | None = None
    etymology_root: str | None = None
    origin_language: str | None = None
    language_family: str | None = None
    historical_context: str | None = None
    confidence: str = "low"      # low | medium | high
    source_agent: str | None = None

    def is_complete(self) -> bool:
        return bool(self.origin_language and self.etymology_root)


# ---------------------------------------------------------------------------
# ISO 639-3 code → (human name, language family)
# ---------------------------------------------------------------------------
ISO_TO_LANGUAGE: dict[str, tuple[str, str]] = {
    # Germanic
    "eng": ("English",                 "Indo-European (Germanic)"),
    "enm": ("Middle English",          "Indo-European (Germanic)"),
    "ang": ("Old English",             "Indo-European (Germanic)"),
    "non": ("Old Norse",               "Indo-European (Germanic)"),
    "deu": ("German",                  "Indo-European (Germanic)"),
    "gmh": ("Middle High German",      "Indo-European (Germanic)"),
    "goh": ("Old High German",         "Indo-European (Germanic)"),
    "nld": ("Dutch",                   "Indo-European (Germanic)"),
    "dum": ("Middle Dutch",            "Indo-European (Germanic)"),
    "fry": ("Frisian",                 "Indo-European (Germanic)"),
    "sco": ("Scots",                   "Indo-European (Germanic)"),
    "isl": ("Icelandic",               "Indo-European (Germanic)"),
    "dan": ("Danish",                  "Indo-European (Germanic)"),
    "swe": ("Swedish",                 "Indo-European (Germanic)"),
    "nob": ("Norwegian",               "Indo-European (Germanic)"),
    "got": ("Gothic",                  "Indo-European (Germanic)"),
    "yid": ("Yiddish",                 "Indo-European (Germanic)"),
    "afr": ("Afrikaans",               "Indo-European (Germanic)"),
    "gem": ("Proto-Germanic",          "Indo-European (Germanic)"),
    # Romance
    "lat": ("Latin",                   "Indo-European (Italic)"),
    "fra": ("French",                  "Indo-European (Romance)"),
    "fro": ("Old French",              "Indo-European (Romance)"),
    "frm": ("Middle French",           "Indo-European (Romance)"),
    "xno": ("Anglo-Norman",            "Indo-European (Romance)"),
    "ita": ("Italian",                 "Indo-European (Romance)"),
    "spa": ("Spanish",                 "Indo-European (Romance)"),
    "por": ("Portuguese",              "Indo-European (Romance)"),
    "rum": ("Romanian",                "Indo-European (Romance)"),
    "pro": ("Old Provençal",           "Indo-European (Romance)"),
    "cat": ("Catalan",                 "Indo-European (Romance)"),
    "oci": ("Occitan",                 "Indo-European (Romance)"),
    # Greek
    "grc": ("Ancient Greek",           "Indo-European (Hellenic)"),
    "ell": ("Modern Greek",            "Indo-European (Hellenic)"),
    # Indo-Iranian
    "san": ("Sanskrit",                "Indo-European (Indo-Iranian)"),
    "hin": ("Hindi",                   "Indo-European (Indo-Iranian)"),
    "urd": ("Urdu",                    "Indo-European (Indo-Iranian)"),
    "per": ("Persian",                 "Indo-European (Indo-Iranian)"),
    "pli": ("Pali",                    "Indo-European (Indo-Iranian)"),
    "awa": ("Avestan",                 "Indo-European (Indo-Iranian)"),
    # Celtic
    "gle": ("Irish",                   "Indo-European (Celtic)"),
    "gla": ("Scottish Gaelic",         "Indo-European (Celtic)"),
    "wel": ("Welsh",                   "Indo-European (Celtic)"),
    "bre": ("Breton",                  "Indo-European (Celtic)"),
    "cor": ("Cornish",                 "Indo-European (Celtic)"),
    "cel": ("Proto-Celtic",            "Indo-European (Celtic)"),
    "sga": ("Old Irish",               "Indo-European (Celtic)"),
    # Slavic
    "rus": ("Russian",                 "Indo-European (Slavic)"),
    "pol": ("Polish",                  "Indo-European (Slavic)"),
    "ces": ("Czech",                   "Indo-European (Slavic)"),
    "chu": ("Old Church Slavonic",     "Indo-European (Slavic)"),
    # Baltic
    "lit": ("Lithuanian",              "Indo-European (Baltic)"),
    "lav": ("Latvian",                 "Indo-European (Baltic)"),
    "prg": ("Old Prussian",            "Indo-European (Baltic)"),
    # Proto-Indo-European
    "ine": ("Proto-Indo-European",     "Proto-Indo-European"),
    "pie": ("Proto-Indo-European",     "Proto-Indo-European"),
    # Semitic / Afro-Asiatic
    "ara": ("Arabic",                  "Afro-Asiatic (Semitic)"),
    "heb": ("Hebrew",                  "Afro-Asiatic (Semitic)"),
    "arc": ("Aramaic",                 "Afro-Asiatic (Semitic)"),
    "syc": ("Syriac",                  "Afro-Asiatic (Semitic)"),
    "amh": ("Amharic",                 "Afro-Asiatic (Semitic)"),
    # Turkic
    "tur": ("Turkish",                 "Turkic"),
    "aze": ("Azerbaijani",             "Turkic"),
    "kaz": ("Kazakh",                  "Turkic"),
    "uzb": ("Uzbek",                   "Turkic"),
    # Japonic / Koreanic / Sino-Tibetan
    "jpn": ("Japanese",                "Japonic"),
    "kor": ("Korean",                  "Koreanic"),
    "zho": ("Chinese",                 "Sino-Tibetan"),
    "cmn": ("Mandarin Chinese",        "Sino-Tibetan"),
    # Austronesian
    "msa": ("Malay",                   "Austronesian"),
    "zsm": ("Malay",                   "Austronesian"),
    "ind": ("Indonesian",              "Austronesian"),
    "tgl": ("Tagalog",                 "Austronesian"),
    "haw": ("Hawaiian",                "Austronesian (Polynesian)"),
    "mri": ("Maori",                   "Austronesian (Polynesian)"),
    "fij": ("Fijian",                  "Austronesian (Polynesian)"),
    # Dravidian
    "tam": ("Tamil",                   "Dravidian"),
    "tel": ("Telugu",                  "Dravidian"),
    "mal": ("Malayalam",               "Dravidian"),
    "kan": ("Kannada",                 "Dravidian"),
    # Uralic
    "fin": ("Finnish",                 "Uralic (Finnic)"),
    "est": ("Estonian",                "Uralic (Finnic)"),
    "hun": ("Hungarian",               "Uralic (Ugric)"),
    "lpi": ("Sami",                    "Uralic (Sami)"),
    # Niger-Congo
    "swa": ("Swahili",                 "Niger-Congo (Bantu)"),
    "yor": ("Yoruba",                  "Niger-Congo"),
    "zul": ("Zulu",                    "Niger-Congo (Bantu)"),
    # Amerindian
    "nah": ("Nahuatl",                 "Uto-Aztecan"),
    "que": ("Quechua",                 "Quechuan"),
    "tup": ("Tupi",                    "Tupian"),
    "alg": ("Algonquian",              "Algic"),
    # Other / isolates
    "baq": ("Basque",                  "Language isolate"),
    "geo": ("Georgian",                "Kartvelian"),
    "egy": ("Ancient Egyptian",        "Afro-Asiatic"),
    "cop": ("Coptic",                  "Afro-Asiatic"),
}

# ---------------------------------------------------------------------------
# Collins definition hint text → (origin_language, language_family)
# Hints that are NOT language names (register, region, author) are excluded.
# ---------------------------------------------------------------------------
COLLINS_HINT_TO_LANGUAGE: dict[str, tuple[str, str]] = {
    "French":           ("French",              "Indo-European (Romance)"),
    "Old French":       ("Old French",           "Indo-European (Romance)"),
    "Middle French":    ("Middle French",        "Indo-European (Romance)"),
    "Anglo-French":     ("Anglo-Norman",         "Indo-European (Romance)"),
    "Norman French":    ("Anglo-Norman",         "Indo-European (Romance)"),
    "Latin":            ("Latin",                "Indo-European (Italic)"),
    "Medieval Latin":   ("Medieval Latin",       "Indo-European (Italic)"),
    "New Latin":        ("New Latin",            "Indo-European (Italic)"),
    "Greek":            ("Ancient Greek",        "Indo-European (Hellenic)"),
    "Italian":          ("Italian",              "Indo-European (Romance)"),
    "Spanish":          ("Spanish",              "Indo-European (Romance)"),
    "Portuguese":       ("Portuguese",           "Indo-European (Romance)"),
    "German":           ("German",               "Indo-European (Germanic)"),
    "Middle High German": ("Middle High German", "Indo-European (Germanic)"),
    "Dutch":            ("Dutch",                "Indo-European (Germanic)"),
    "Old Norse":        ("Old Norse",            "Indo-European (Germanic)"),
    "Old English":      ("Old English",          "Indo-European (Germanic)"),
    "Middle English":   ("Middle English",       "Indo-European (Germanic)"),
    "Scots":            ("Scots",                "Indo-European (Germanic)"),
    "Scottish":         ("Scots",                "Indo-European (Germanic)"),
    "Gaelic":           ("Scottish Gaelic",      "Indo-European (Celtic)"),
    "Irish":            ("Irish",                "Indo-European (Celtic)"),
    "Welsh":            ("Welsh",                "Indo-European (Celtic)"),
    "Hindi":            ("Hindi",                "Indo-European (Indo-Iranian)"),
    "Urdu":             ("Urdu",                 "Indo-European (Indo-Iranian)"),
    "Sanskrit":         ("Sanskrit",             "Indo-European (Indo-Iranian)"),
    "Persian":          ("Persian",              "Indo-European (Indo-Iranian)"),
    "Arabic":           ("Arabic",               "Afro-Asiatic (Semitic)"),
    "Hebrew":           ("Hebrew",               "Afro-Asiatic (Semitic)"),
    "Turkish":          ("Turkish",              "Turkic"),
    "Japanese":         ("Japanese",             "Japonic"),
    "Chinese":          ("Chinese",              "Sino-Tibetan"),
    "Russian":          ("Russian",              "Indo-European (Slavic)"),
    "Malay":            ("Malay",                "Austronesian"),
    "Hawaiian":         ("Hawaiian",             "Austronesian (Polynesian)"),
    "Maori":            ("Maori",                "Austronesian (Polynesian)"),
    "Tagalog":          ("Tagalog",              "Austronesian"),
    "Yiddish":          ("Yiddish",              "Indo-European (Germanic)"),
    "Afrikaans":        ("Afrikaans",            "Indo-European (Germanic)"),
    "South African":    ("Afrikaans",            "Indo-European (Germanic)"),
    "Nahuatl":          ("Nahuatl",              "Uto-Aztecan"),
    "Tupi":             ("Tupi",                 "Tupian"),
    "Quechua":          ("Quechua",              "Quechuan"),
    "Tamil":            ("Tamil",                "Dravidian"),
    "Swahili":          ("Swahili",              "Niger-Congo (Bantu)"),
    "Finnish":          ("Finnish",              "Uralic (Finnic)"),
    "Hungarian":        ("Hungarian",            "Uralic (Ugric)"),
    "Basque":           ("Basque",               "Language isolate"),
    "Aboriginal":       ("Australian Aboriginal","Pama-Nyungan"),
    "Native Australian": ("Australian Aboriginal","Pama-Nyungan"),
    "Australian Aboriginal": ("Australian Aboriginal", "Pama-Nyungan"),
}
