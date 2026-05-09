"""
Seed the Living Lexicon with curated historical words and foundational Words/ CSV data.
Run: python -m ingestor.seed_data

Idempotent — safe to run multiple times. All writes use MERGE.
"""
from dataclasses import replace

from ingestor.graph_loader import LexiconIngestor, WordEntry
from ingestor.seed_db_importer import (
    SEED_DATABASE_V1,
    SEED_DATABASE_V2,
    build_seed_db_word_entries,
    load_seed_db_records,
)
from ingestor.sources_catalog import ALL_SOURCES

# ── 7 Canonical Era Nodes ─────────────────────────────────────────────────────

ERAS = [
    {
        "name": "Proto-Indo-European",
        "start_year": -4500, "end_year": -2500,
        "summary": "The reconstructed ancestor language of most European and South Asian languages. No written records survive — forms are inferred by comparing daughter languages.",
        "register": "scholarly",
    },
    {
        "name": "Classical Latin",
        "start_year": -200, "end_year": 400,
        "summary": "Rome at peak influence. Latin vocabulary entered English through the Church, law, and scholarship. Most English academic and medical vocabulary traces here.",
        "register": "legal | scholarly | religious",
    },
    {
        "name": "Old English",
        "start_year": 450, "end_year": 1150,
        "summary": "Anglo-Saxon English before the Norman Conquest. Most core English words (house, eat, sleep, god) are Old English. Latin words entered through the Church.",
        "register": "general | religious",
    },
    {
        "name": "Middle English",
        "start_year": 1150, "end_year": 1470,
        "summary": "Chaucer's era. After the Norman Conquest, French flooded English with thousands of words. Old English and French fused into Middle English.",
        "register": "general | literary | legal",
    },
    {
        "name": "Early Modern English",
        "start_year": 1470, "end_year": 1700,
        "summary": "The era of the King James Bible (1611), Shakespeare's plays (1590–1613), and the codification of English legal register. Many words carried meanings that have since reversed or narrowed dramatically.",
        "register": "biblical | literary | legal",
    },
    {
        "name": "18th-19th Century English",
        "start_year": 1700, "end_year": 1900,
        "summary": "The Industrial Revolution, Enlightenment, and British Empire drove massive vocabulary expansion and semantic specialization. Many words narrowed from general to technical meanings.",
        "register": "general | scientific | literary",
    },
    {
        "name": "Modern English",
        "start_year": 1900, "end_year": 2026,
        "summary": "Current English. Words have often softened, narrowed, or reversed from their Early Modern forms. This is the meaning most readers bring to old texts — and the source of most misreadings.",
        "register": "general",
    },
]

# ── 22 Seed Words ─────────────────────────────────────────────────────────────

SEED_WORDS = [

    # ── Cluster 1: Latin pati (to suffer/endure) ──────────────────────────────

    WordEntry(
        name="compassion", language="English",
        definition="A feeling of sympathy and sorrow for the suffering of others, with a desire to help.",
        root_name="pati", root_meaning="to suffer, to endure", root_origin_language="Classical Latin",
        attested_year=1340,
        cognates=["patient", "passion", "passive", "compatible", "impatient"],
        era_meanings=[
            {"era_name": "Classical Latin", "meaning": "shared suffering; literally 'suffering together' (com- + pati)",
             "usage_example": None, "register": "scholarly", "source": "de-vaan-2008", "confidence": "high"},
            {"era_name": "Middle English", "meaning": "physical or spiritual co-suffering; feeling another's pain as your own bodily experience",
             "usage_example": "Wycliffe: 'He had compassion on them' — meaning he felt their pain within himself",
             "register": "religious", "source": "wycliffe-1382", "confidence": "high"},
            {"era_name": "Early Modern English", "meaning": "suffering alongside another; empathetic pain (still physical in connotation)",
             "usage_example": "KJV Matthew 9:36: 'he was moved with compassion' — not merely sympathy but gut-level distress",
             "register": "biblical", "source": "kjv-1611", "confidence": "high"},
            {"era_name": "Modern English", "meaning": "warm emotional sympathy; concern for others' suffering (physical dimension largely lost)",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    WordEntry(
        name="patient", language="English",
        definition="A person receiving medical treatment; or, calmly tolerant of delay or suffering.",
        root_name="pati", root_meaning="to suffer, to endure", root_origin_language="Classical Latin",
        attested_year=1374,
        cognates=["compassion", "passion", "passive", "compatible"],
        era_meanings=[
            {"era_name": "Classical Latin", "meaning": "one who endures or suffers (patiens, patienti-)",
             "usage_example": None, "register": "general", "source": "de-vaan-2008", "confidence": "high"},
            {"era_name": "Early Modern English", "meaning": "one who bears suffering with calm endurance; not yet narrowed to medical use",
             "usage_example": "Shakespeare: 'Be patient' — commanding endurance, not advising someone to wait calmly",
             "register": "literary", "source": "shakespeare", "confidence": "high"},
            {"era_name": "18th-19th Century English", "meaning": "narrowed to medical context: a person under a doctor's care",
             "usage_example": None, "register": "scientific", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    WordEntry(
        name="passion", language="English",
        definition="Strong romantic or sexual feeling; intense enthusiasm.",
        root_name="pati", root_meaning="to suffer, to endure", root_origin_language="Classical Latin",
        attested_year=1175,
        cognates=["compassion", "patient", "passive", "compatible"],
        era_meanings=[
            {"era_name": "Classical Latin", "meaning": "suffering, physical ordeal (passio)",
             "usage_example": None, "register": "religious", "source": "de-vaan-2008", "confidence": "high"},
            {"era_name": "Middle English", "meaning": "the physical suffering and death of Jesus Christ on the cross",
             "usage_example": "The Passion of Christ — his torment and crucifixion",
             "register": "religious", "source": "niermeyer-1976", "confidence": "high"},
            {"era_name": "Early Modern English", "meaning": "any overwhelming emotion that controls you — grief, rage, love, fear (you are its victim)",
             "usage_example": "Shakespeare: 'What passion hangs these weights upon my tongue?' — overpowering emotion",
             "register": "literary", "source": "shakespeare", "confidence": "high"},
            {"era_name": "Modern English", "meaning": "intense romantic or sexual feeling; strong enthusiasm for something",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    WordEntry(
        name="passive", language="English",
        definition="Accepting what happens without active response; submissive; not active.",
        root_name="pati", root_meaning="to suffer, to endure", root_origin_language="Classical Latin",
        attested_year=1483,
        cognates=["compassion", "patient", "passion", "compatible"],
        era_meanings=[
            {"era_name": "Classical Latin", "meaning": "acted upon; the one who receives action (grammatical term: passive voice)",
             "usage_example": None, "register": "scholarly", "source": "de-vaan-2008", "confidence": "high"},
            {"era_name": "Modern English", "meaning": "apathetic, inactive, submissive — pejorative connotation of weakness",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    WordEntry(
        name="compatible", language="English",
        definition="Able to exist or work together without conflict.",
        root_name="pati", root_meaning="to suffer, to endure", root_origin_language="Classical Latin",
        attested_year=1489,
        cognates=["compassion", "patient", "passion", "passive"],
        era_meanings=[
            {"era_name": "Classical Latin", "meaning": "able to endure together; capable of co-suffering (com- + pati)",
             "usage_example": None, "register": "scholarly", "source": "de-vaan-2008", "confidence": "high"},
            {"era_name": "Modern English", "meaning": "technically or socially fitting; able to function together",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    # ── Cluster 2: KJV false-friends ─────────────────────────────────────────

    WordEntry(
        name="prevent", language="English",
        definition="To stop something from happening before it occurs.",
        root_name="praevenire", root_meaning="to come before, to precede", root_origin_language="Classical Latin",
        attested_year=1425,
        cognates=["prevention", "venue", "avenue", "advent", "convention", "event"],
        era_meanings=[
            {"era_name": "Classical Latin", "meaning": "to come before; to arrive ahead of (prae = before + venire = to come)",
             "usage_example": None, "register": "general", "source": "de-vaan-2008", "confidence": "high"},
            {"era_name": "Early Modern English", "meaning": "to come before; to precede; to anticipate (no blocking sense)",
             "usage_example": 'KJV Psalms 119:147: "I prevented the dawning of the morning" (= I arose before dawn)',
             "register": "biblical", "source": "kjv-1611", "confidence": "high"},
            {"era_name": "18th-19th Century English", "meaning": "shifting toward obstruction: to anticipate in order to hinder",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "medium"},
            {"era_name": "Modern English", "meaning": "to stop something from happening; to forestall",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    WordEntry(
        name="let", language="English",
        definition="To allow or permit.",
        root_name="lettan", root_meaning="to hinder, to obstruct", root_origin_language="Old English",
        attested_year=900,
        cognates=["hindrance", "delay"],
        era_meanings=[
            {"era_name": "Old English", "meaning": "to hinder, to obstruct, to delay",
             "usage_example": None, "register": "general", "source": "hall-1894", "confidence": "high"},
            {"era_name": "Early Modern English", "meaning": "to hinder or obstruct (opposite of modern meaning)",
             "usage_example": 'KJV Romans 1:13: "I was let hitherto" (= I was hindered/prevented from coming)',
             "register": "biblical", "source": "kjv-1611", "confidence": "high"},
            {"era_name": "Modern English", "meaning": "to allow or permit (complete reversal from original meaning)",
             "usage_example": 'The only survival of the old meaning: "without let or hindrance" in legal/passport language',
             "register": "general", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    WordEntry(
        name="conversation", language="English",
        definition="A spoken exchange of thoughts between people.",
        root_name="conversatio", root_meaning="manner of life, conduct, social behavior", root_origin_language="Classical Latin",
        attested_year=1340,
        cognates=["convert", "converse", "verse", "universe"],
        era_meanings=[
            {"era_name": "Classical Latin", "meaning": "manner of living; conduct; the way one moves through society (conversatio)",
             "usage_example": None, "register": "general", "source": "de-vaan-2008", "confidence": "high"},
            {"era_name": "Early Modern English", "meaning": "manner of life; social conduct; behavior and moral character",
             "usage_example": 'KJV Philippians 1:27: "let your conversation be as it becometh the gospel" (= let your conduct be worthy)',
             "register": "biblical", "source": "kjv-1611", "confidence": "high"},
            {"era_name": "18th-19th Century English", "meaning": "narrowed to verbal exchange between people",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    WordEntry(
        name="charity", language="English",
        definition="Giving money or help to those in need; an organization that does so.",
        root_name="caritas", root_meaning="Christian love; love of God and neighbor", root_origin_language="Classical Latin",
        attested_year=1225,
        cognates=["cherish", "dear", "caress"],
        era_meanings=[
            {"era_name": "Classical Latin", "meaning": "caritas: the highest Christian love; selfless, unconditional love of God and humanity (distinct from eros/romantic love)",
             "usage_example": None, "register": "religious", "source": "vulgate-latin", "confidence": "high"},
            {"era_name": "Early Modern English", "meaning": "love (agape) — the Greek word for God's unconditional love for humanity",
             "usage_example": 'KJV 1 Corinthians 13:1: "Though I speak with tongues of men and angels, and have not charity, I am become as sounding brass" (modern Bibles use "love")',
             "register": "biblical", "source": "kjv-1611", "confidence": "high"},
            {"era_name": "18th-19th Century English", "meaning": "narrowed to benevolent giving to the poor; almsgiving",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "high"},
            {"era_name": "Modern English", "meaning": "an organization that helps the poor; the act of donating money",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    WordEntry(
        name="quick", language="English",
        definition="Moving fast; rapid.",
        root_name="cwic", root_meaning="alive, living", root_origin_language="Old English",
        attested_year=888,
        cognates=["quicksilver", "quicksand", "quicken"],
        era_meanings=[
            {"era_name": "Old English", "meaning": "alive, living (cwic); the opposite of dead",
             "usage_example": None, "register": "general", "source": "hall-1894", "confidence": "high"},
            {"era_name": "Early Modern English", "meaning": "alive and active; living (not yet 'fast')",
             "usage_example": 'KJV Hebrews 4:12: "the word of God is quick, and powerful" (= alive and active, not speedy)',
             "register": "biblical", "source": "kjv-1611", "confidence": "high"},
            {"era_name": "18th-19th Century English", "meaning": "lively → shifting to rapid, fast",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "medium"},
            {"era_name": "Modern English", "meaning": "fast, rapid (the 'alive' sense survives only in 'the quick and the dead' and 'quicken')",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    WordEntry(
        name="naughty", language="English",
        definition="Badly behaved; disobedient (usually of children); mildly rude or indecent.",
        root_name="naught", root_meaning="nothing, worthless", root_origin_language="Old English",
        attested_year=1350,
        cognates=["naught", "nought"],
        era_meanings=[
            {"era_name": "Middle English", "meaning": "having nothing; worthless; wicked (from 'naught' = nothing)",
             "usage_example": None, "register": "general", "source": "mec-corpus", "confidence": "high"},
            {"era_name": "Early Modern English", "meaning": "morally wicked; villainous; evil",
             "usage_example": 'KJV Proverbs 6:12: "A naughty person, a wicked man, walketh with a froward mouth" (= a genuinely evil villain, not a misbehaving child)',
             "register": "biblical", "source": "kjv-1611", "confidence": "high"},
            {"era_name": "18th-19th Century English", "meaning": "weakening: mildly disobedient; especially of children",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "high"},
            {"era_name": "Modern English", "meaning": "mildly disobedient (of children) or mildly indecent; much weaker than original",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    WordEntry(
        name="carriage", language="English",
        definition="A wheeled vehicle pulled by horses.",
        root_name="cariage", root_meaning="things carried; baggage; the act of carrying", root_origin_language="Middle English",
        attested_year=1330,
        cognates=["carry", "cargo", "carrier"],
        era_meanings=[
            {"era_name": "Middle English", "meaning": "the act of carrying; baggage; things being transported",
             "usage_example": None, "register": "general", "source": "mec-corpus", "confidence": "high"},
            {"era_name": "Early Modern English", "meaning": "baggage; things carried on a journey",
             "usage_example": 'KJV Acts 21:15: "we took up our carriages, and went up to Jerusalem" (= we packed our bags)',
             "register": "biblical", "source": "kjv-1611", "confidence": "high"},
            {"era_name": "18th-19th Century English", "meaning": "shifted to the vehicle that carries people: a horse-drawn carriage",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    WordEntry(
        name="succor", language="English",
        definition="Assistance and support in times of hardship (archaic/literary).",
        root_name="succurrere", root_meaning="to run beneath, to run to help", root_origin_language="Classical Latin",
        attested_year=1250,
        cognates=["occur", "current", "currency", "courier"],
        era_meanings=[
            {"era_name": "Classical Latin", "meaning": "to run beneath/to; to come to the aid of (sub + currere = under + run)",
             "usage_example": None, "register": "general", "source": "de-vaan-2008", "confidence": "high"},
            {"era_name": "Early Modern English", "meaning": "to aid, assist, relieve someone in distress",
             "usage_example": 'KJV Hebrews 2:18: "he is able to succour them that are tempted"',
             "register": "biblical", "source": "kjv-1611", "confidence": "high"},
            {"era_name": "Modern English", "meaning": "archaic/literary: to give aid or relief. The root sense (running to help) has been forgotten.",
             "usage_example": None, "register": "literary", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    # ── Cluster 3: Shakespeare register words ────────────────────────────────

    WordEntry(
        name="honest", language="English",
        definition="Truthful; not lying or cheating.",
        root_name="honestus", root_meaning="honorable, respectable, of good standing", root_origin_language="Classical Latin",
        attested_year=1300,
        cognates=["honor", "honorary", "honesty"],
        era_meanings=[
            {"era_name": "Classical Latin", "meaning": "honorable, respectable, of high social standing (honestus)",
             "usage_example": None, "register": "general", "source": "de-vaan-2008", "confidence": "high"},
            {"era_name": "Early Modern English", "meaning": "honorable, respectable, chaste — especially applied to women's sexual virtue or men's social standing",
             "usage_example": 'Shakespeare Othello: "I am not what I am" — Iago\'s "honest" is a title of social honor, not mere truthfulness',
             "register": "literary", "source": "shakespeare", "confidence": "high"},
            {"era_name": "Modern English", "meaning": "truthful; not lying or cheating (narrowed from social honor to verbal truthfulness)",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    WordEntry(
        name="artificial", language="English",
        definition="Made by humans, not occurring naturally; fake or contrived.",
        root_name="artificialis", root_meaning="made with artistry or skill", root_origin_language="Classical Latin",
        attested_year=1400,
        cognates=["art", "artifact", "artisan", "artful"],
        era_meanings=[
            {"era_name": "Classical Latin", "meaning": "made with great skill and artistry; the product of craft (ars + facere = art + to make)",
             "usage_example": None, "register": "scholarly", "source": "de-vaan-2008", "confidence": "high"},
            {"era_name": "Early Modern English", "meaning": "skillfully made; artistically crafted — a compliment",
             "usage_example": "Shakespeare: 'What an artificial night this is!' — meaning wonderfully, skilfully constructed",
             "register": "literary", "source": "shakespeare", "confidence": "high"},
            {"era_name": "18th-19th Century English", "meaning": "beginning to shift toward 'not natural'; synthetic",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "medium"},
            {"era_name": "Modern English", "meaning": "fake, synthetic, not genuine — now often pejorative",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    WordEntry(
        name="counterfeit", language="English",
        definition="Made in exact imitation of something with intent to deceive; fraudulent.",
        root_name="contrefaire", root_meaning="to make a copy; to portray, depict", root_origin_language="Middle English",
        attested_year=1300,
        cognates=["fact", "factory", "fashion", "feature"],
        era_meanings=[
            {"era_name": "Middle English", "meaning": "to portray or depict; to represent artistically (from Old French contrefaire = to copy/imitate)",
             "usage_example": None, "register": "general", "source": "mec-corpus", "confidence": "high"},
            {"era_name": "Early Modern English", "meaning": "to represent; to portray — still neutral or positive",
             "usage_example": "Shakespeare: 'I will counterfeit the bewitchment of some popular man' — meaning 'imitate', not 'forge fraudulently'",
             "register": "literary", "source": "shakespeare", "confidence": "high"},
            {"era_name": "Modern English", "meaning": "fraudulent imitation; forgery with intent to deceive",
             "usage_example": None, "register": "legal", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    WordEntry(
        name="fond", language="English",
        definition="Having an affection or liking for someone or something.",
        root_name="fonne", root_meaning="foolish, doting, infatuated", root_origin_language="Middle English",
        attested_year=1390,
        cognates=["fool", "folly"],
        era_meanings=[
            {"era_name": "Middle English", "meaning": "foolish, doting, simple-minded (fonne = fool)",
             "usage_example": None, "register": "general", "source": "mec-corpus", "confidence": "high"},
            {"era_name": "Early Modern English", "meaning": "foolishly in love; doting to excess; naive",
             "usage_example": "Shakespeare: 'I am too fond' — meaning too foolishly in love, not simply affectionate",
             "register": "literary", "source": "shakespeare", "confidence": "high"},
            {"era_name": "Modern English", "meaning": "affectionate, loving — the 'foolish' sense has been lost",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    # ── Cluster 4: PIE ghos-ti (stranger) ────────────────────────────────────

    WordEntry(
        name="host", language="English",
        definition="A person who receives or entertains guests.",
        root_name="ghos-ti", root_meaning="stranger, guest, foreigner", root_origin_language="Proto-Indo-European",
        attested_year=1290,
        cognates=["hostile", "guest", "hospital", "hospice", "hostage"],
        era_meanings=[
            {"era_name": "Proto-Indo-European", "meaning": "stranger; guest; foreigner — the person who stands in a defined reciprocal relationship of exchange",
             "usage_example": None, "register": "scholarly", "source": "watkins-pie-2000", "confidence": "medium"},
            {"era_name": "Classical Latin", "meaning": "hospes (host) and hostis (enemy) — the same root split into those who receive strangers and those who oppose them",
             "usage_example": None, "register": "scholarly", "source": "de-vaan-2008", "confidence": "high"},
            {"era_name": "Modern English", "meaning": "one who receives and entertains guests; the welcoming side of the host-guest relationship",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    WordEntry(
        name="hostile", language="English",
        definition="Unfriendly; antagonistic; of or relating to an enemy.",
        root_name="ghos-ti", root_meaning="stranger, guest, foreigner", root_origin_language="Proto-Indo-European",
        attested_year=1590,
        cognates=["host", "guest", "hospital", "hospice", "hostage"],
        era_meanings=[
            {"era_name": "Classical Latin", "meaning": "hostilis: of or belonging to an enemy (hostis = enemy — evolved from 'stranger' to 'enemy' as Rome defined outsiders as threats)",
             "usage_example": None, "register": "legal | military", "source": "de-vaan-2008", "confidence": "high"},
            {"era_name": "Modern English", "meaning": "unfriendly, antagonistic — still carrying the 'enemy-stranger' branch of the original PIE root",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    WordEntry(
        name="guest", language="English",
        definition="A person who is invited to visit or stay at someone's home.",
        root_name="ghos-ti", root_meaning="stranger, guest, foreigner", root_origin_language="Proto-Indo-European",
        attested_year=1290,
        cognates=["host", "hostile", "hospital", "hospice", "hostage"],
        era_meanings=[
            {"era_name": "Old English", "meaning": "gæst: stranger, guest — the receiving side of the host-stranger exchange",
             "usage_example": None, "register": "general", "source": "hall-1894", "confidence": "high"},
            {"era_name": "Modern English", "meaning": "invited visitor; person staying temporarily",
             "usage_example": None, "register": "general", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    WordEntry(
        name="hospital", language="English",
        definition="An institution providing medical treatment and nursing care.",
        root_name="ghos-ti", root_meaning="stranger, guest, foreigner", root_origin_language="Proto-Indo-European",
        attested_year=1300,
        cognates=["host", "hostile", "guest", "hospice", "hotel", "hostel"],
        era_meanings=[
            {"era_name": "Classical Latin", "meaning": "hospitale: a place for receiving guests and strangers (hospitality for travelers, pilgrims, the poor)",
             "usage_example": None, "register": "religious | general", "source": "niermeyer-1976", "confidence": "high"},
            {"era_name": "Middle English", "meaning": "a house of hospitality — receiving pilgrims, travelers, the sick, and the poor indiscriminately",
             "usage_example": None, "register": "religious", "source": "mec-corpus", "confidence": "high"},
            {"era_name": "18th-19th Century English", "meaning": "narrowed to medical care specifically; the sick-reception function dominated",
             "usage_example": None, "register": "scientific", "source": "oed-2e", "confidence": "high"},
        ],
    ),

    WordEntry(
        name="hospice", language="English",
        definition="A facility providing care for the terminally ill.",
        root_name="ghos-ti", root_meaning="stranger, guest, foreigner", root_origin_language="Proto-Indo-European",
        attested_year=1818,
        cognates=["host", "hostile", "guest", "hospital", "hotel"],
        era_meanings=[
            {"era_name": "Classical Latin", "meaning": "hospitium: place of hospitality for travelers and the weary (same root as hospital, hotel, hostel)",
             "usage_example": None, "register": "religious", "source": "de-vaan-2008", "confidence": "high"},
            {"era_name": "18th-19th Century English", "meaning": "a house of rest for travelers or pilgrims; especially monastic guest houses",
             "usage_example": None, "register": "religious", "source": "oed-2e", "confidence": "high"},
            {"era_name": "Modern English", "meaning": "narrowed to care for the dying; end-of-life comfort facility",
             "usage_example": None, "register": "medical", "source": "oed-2e", "confidence": "high"},
        ],
    ),
]


def _word_key(entry: WordEntry) -> tuple[str, str]:
    """Case-insensitive identity for preventing duplicate Word nodes."""
    return (entry.name.strip().casefold(), entry.language.strip().casefold())


def _canonical_words_folder_entry(entry: WordEntry) -> WordEntry:
    """Keep Words/ CSV entries aligned with the lowercase curated seed words."""
    return replace(entry, name=entry.name.strip().casefold())


def load_words_folder_seed_words() -> list[WordEntry]:
    """Load the small foundational word CSVs from Words/ into seed entries."""
    records = []
    for path in (SEED_DATABASE_V1, SEED_DATABASE_V2):
        records.extend(load_seed_db_records(str(path)))
    return [
        _canonical_words_folder_entry(entry)
        for entry in build_seed_db_word_entries(records)
    ]


def build_seed_words() -> list[WordEntry]:
    """Combine curated seed words with Words/ CSV entries, keeping curated data first."""
    entries = list(SEED_WORDS)
    seen = {_word_key(entry) for entry in entries}

    for entry in load_words_folder_seed_words():
        key = _word_key(entry)
        if key in seen:
            continue
        seen.add(key)
        entries.append(entry)

    return entries


def seed():
    ingestor = LexiconIngestor()
    ingestor.ensure_indexes()

    print(f"[seed] Loading {len(ALL_SOURCES)} Source nodes...")
    for source in ALL_SOURCES:
        ingestor.ingest_source(source)
    print("[seed] Source nodes ready.")

    print("[seed] Creating 7 Era nodes...")
    for era in ERAS:
        ingestor.ingest_era_node(era)
    print("[seed] Era nodes ready.")

    seed_words = build_seed_words()
    extra_words = len(seed_words) - len(SEED_WORDS)
    print(f"[seed] Loaded {extra_words} additional words from Words/ seed CSVs.")

    print(f"[seed] Ingesting {len(seed_words)} words with era meanings...")
    results = ingestor.bulk_ingest(seed_words)

    # Wire ATTESTED_IN edges from each word to its era meaning sources
    print("[seed] Wiring ATTESTED_IN source edges...")
    for entry in seed_words:
        seen_slugs: set[str] = set()
        for em in (entry.era_meanings or []):
            slug = em.get("source")
            if slug and slug not in seen_slugs:
                try:
                    ingestor.write_attested_in(entry.name, entry.language, slug)
                    seen_slugs.add(slug)
                except Exception:
                    pass  # Source node may not exist yet for unmapped slugs

    ingestor.close()

    print(f"[seed] Done — ingested={results['ingested']}, failed={results['failed']}")
    if results["errors"]:
        for err in results["errors"]:
            print(f"  ERROR: {err['word']}: {err['error']}")


if __name__ == "__main__":
    seed()
