# Living Lexicon — Claude Context

## Architecture

```
the-living-lexicon/
├── living_lexicon/          # SDK (pip-installable)
│   ├── core.py              # WordHistorian — single entry point
│   ├── protocols.py         # EtymologyStore, LLMProvider protocols
│   ├── models.py            # Pure dataclasses (WordContext, EraRecord, ...)
│   ├── vitality.py          # compute_vitality() — V = 0.4·S + 0.4·D + 0.2·A (authority-weighted)
│   ├── citation_formatter.py  # to_bibtex/to_apa/to_mla/to_chicago — pure, no DB
│   ├── etymology_path.py    # build_etymology_path() — pure step-by-step etymology builder
│   ├── prompts.py           # build_drift_prompt(), build_era_explanation_prompt()
│   ├── config.py            # LexiconConfig (reads env vars)
│   ├── exceptions.py        # LexiconError hierarchy
│   ├── testing.py           # InMemoryStore, StubLLMProvider, WordHistorianFactory
│   └── providers/
│       ├── stores/
│       │   ├── neo4j_store.py   # Neo4j graph backend (requires neo4j extra)
│       │   └── http_store.py    # HTTP backend (always available)
│       └── llm/
│           └── ollama.py        # Ollama local LLM (requires ollama extra)
├── api/                     # FastAPI app (PostgreSQL relational backend)
│   ├── main.py
│   ├── deps.py              # OllamaProvider/Neo4jStore imports are LAZY (inside fn body)
│   ├── security.py          # require_admin_token(), require_contributor_token()
│   └── routes/
│       ├── pg_words.py      # /pg/word CRUD, vitality, era-check, morphemes, etymology-path
│       ├── pg_senses.py     # /pg/sense, /pg/attestation (+ ?learner_level filter)
│       ├── relations.py     # GET /pg/word/{word}/relations, GET /pg/word/{word}/family,
│       │                    # POST /pg/word/relation (admin)
│       ├── citations.py     # GET /pg/sense/{id}/cite, GET /pg/word/{word}/cite
│       ├── snapshots.py     # POST/GET /pg/snapshots, GET /pg/snapshots/{tag}/export
│       ├── frequency.py     # GET /pg/words/trending
│       ├── semantic_fields.py  # GET /pg/semantic-fields, POST /pg/drift/compare,
│       │                       # GET /pg/word/{word}/drift-trajectory
│       ├── contributions.py # POST /contribute/sense|attestation, GET /contribute/my-submissions
│       └── admin.py         # /ingest, GET /admin/review/pending, PATCH /admin/review/sense/{id}
├── db/                      # SQLAlchemy async ORM
│   ├── database.py
│   ├── models.py            # Word, Sense, Attestation, Source, DatasetSnapshot,
│   │                        # WordRelation, Morpheme tables
│   └── crud.py
├── ingestor/                # Data import scripts
│   ├── base.py              # BaseImporter ABC + ImportResult dataclass
│   ├── utils.py             # clean_str, safe_int, WORD_PATTERN, build_arg_parser
│   ├── senses_importer.py
│   ├── shipley_importer.py
│   ├── gcide_importer.py    # Webster's 1913 — reads gcide-0.54.zip → PostgreSQL
│   ├── frequency_pg_importer.py  # wordfreq Zipf scores → words.wordfreq_zipf
│   ├── morphemes_importer.py    # morphemes CSV → morphemes table (prefix/root/suffix)
│   ├── neo4j_sync.py        # Sync PostgreSQL words/senses → Neo4j graph nodes
│   └── sources_catalog.py
├── alembic/versions/        # 10 migrations (001–010)
├── langchain_plugin/        # LangChain tool wrapper
└── tests/
    ├── conftest.py          # CRUD-monkeypatch fixtures (no SQLite), SDK fixtures
    └── factories.py         # WordPayloadFactory, SensePayloadFactory, ...
```

## Two Storage Backends

| Backend | Purpose | When to Use |
|---|---|---|
| **Neo4j** (`Neo4jStore`) | Graph traversal: cognates, etymology trees, cross-word relationships | SDK consumers, graph queries |
| **PostgreSQL** (`/pg/*` routes) | Relational: senses, attestations, evidence quality, vitality | API consumers, structured queries |

The API (`api/`) writes to PostgreSQL. The SDK (`WordHistorian`) reads from Neo4j (or `InMemoryStore` in tests). They are independent backends; the graph does not mirror the relational store automatically.

## Dev Commands

```bash
make dev              # Start Docker services + app
make test             # Run fast test suite (no Neo4j/Ollama required)
make test-all         # pytest -v across all testpaths
make migrate          # alembic upgrade head
make import-senses    # python -m ingestor.senses_importer
make import-gcide     # python -m ingestor.gcide_importer  (requires Words/gcide-0.54.zip)
make import-frequency # python -m ingestor.frequency_pg_importer  (requires wordfreq)
make sync-neo4j       # python -m ingestor.neo4j_sync  (PostgreSQL → Neo4j)
make make-snapshot    # Prints curl command for POST /pg/snapshots
make lint             # ruff check living_lexicon/ ingestor/ api/ langchain_plugin/
make typecheck        # mypy living_lexicon/
```

## Testing Conventions

**Never** instantiate `Neo4jStore` or `OllamaProvider` in unit tests. Use the zero-dependency stubs:

```python
from living_lexicon.testing import InMemoryStore, StubLLMProvider, WordHistorianFactory
from tests.factories import WordSeedFactory, EraTimelineFactory

store = InMemoryStore(
    words=WordSeedFactory.build_keyed("prevent", root_meaning="to come before"),
    era_timelines=EraTimelineFactory.build_timeline("prevent", {
        "Middle English": "to come before",
        "Early Modern English": "to hinder",
    }),
)
h = WordHistorianFactory.build(store=store, llm_response="It originally meant X.")
ctx = h.context("prevent")
```

The `stub_historian` and `in_memory_store` fixtures in `tests/conftest.py` pre-wire this for "prevent" — use them directly when testing the SDK path.

**HTTP endpoint tests** use `app_client` + `write_headers`. The test client does **not** use SQLite — all `crud.*` functions are monkeypatched with fake async implementations backed by in-memory dicts. Use factory classes:

```python
async def test_create_word(app_client, write_headers, word_payload):
    resp = await app_client.put("/pg/word", json=word_payload.build(), headers=write_headers)
    assert resp.status_code == 200
```

Do **not** import `aiosqlite` or `asyncpg` in tests — the monkeypatch approach makes both unnecessary. If you add a new CRUD function used by an endpoint under test, add a matching patch in `tests/conftest.py`.

## Writing a New Importer

Subclass `BaseImporter` from `ingestor/base.py`:

```python
from pathlib import Path
from ingestor.base import BaseImporter, ImportResult
from ingestor.utils import clean_str, safe_int

class MySourceImporter(BaseImporter):
    source_name = "my-source"
    cli_description = "Import words from My Source CSV."
    default_path = Path("Words/my_source.csv")

    def load(self, path: Path) -> list[dict]:
        import csv
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def ingest(self, records: list[dict], *, dry_run: bool = False) -> ImportResult:
        result = ImportResult(dry_run=dry_run)
        for row in records:
            word = clean_str(row.get("Word"))
            year = safe_int(row.get("Year"))
            if not word:
                result.skipped += 1
                continue
            if not dry_run:
                # ... write to DB
                pass
            result.ingested += 1
        return result

if __name__ == "__main__":
    MySourceImporter().run_cli()
```

`run_cli()` handles argparse, calls `load()` then `ingest()`, prints `result.report()`, and exits with code 1 if `not result.ok`.

## EtymologyStore Protocol (14 methods)

All methods `InMemoryStore` implements — any class satisfying these is a valid store:

```python
# Word graph
get_word(word: str) -> dict | None
get_word_tree(word: str) -> dict
get_cognates(word: str) -> list[dict]
get_etymology_claims(word: str) -> list[dict]
search(query: str, limit: int) -> list[dict]

# Era / timeline
get_word_era_meanings(word: str) -> list[dict]
get_era_timeline(word: str) -> list[dict]
get_word_in_era(word: str, era_name: str) -> dict | None
get_era_by_year(year: int) -> dict | None
get_words_by_era(era_name: str, limit: int) -> list[dict]

# Sources
get_word_sources(word: str) -> list[dict]
get_all_sources() -> list[dict]
get_source(slug: str) -> dict | None
get_words_by_source(slug: str, limit: int) -> list[dict]
```

## Source Authority Tiers

| Tier | Meaning | Examples |
|---|---|---|
| 1 | Primary historical dictionaries | OED, MED, DOST |
| 2 | Authoritative scholarly works | Skeat, Bosworth-Toller |
| 3 | Reference works | Merriam-Webster, Collins |
| 4 | Supplementary | Community sources, personal attestations |

## Canonical Era Names

Used as keys in `era_timelines`, `get_word_in_era()`, and `EraTimelineFactory`:

- `Old English` (–700 to 1066)
- `Middle English` (1066 to 1470)
- `Early Modern English` (1470 to 1700)
- `Late Modern English` (1700 to 1900)
- `20th Century` (1900 to 2000)

## API Access Control

Two separate token tiers, both checked via the `Authorization: Bearer <token>` header:

| Token | Env Var | Controls |
|---|---|---|
| Admin | `ADMIN_API_TOKEN` | `/ingest`, `/admin/review/*`, `POST /pg/snapshots`. Also requires `ENABLE_WRITE_ENDPOINTS=true`. |
| Contributor | `CONTRIBUTOR_API_TOKEN` | `POST /contribute/sense`, `POST /contribute/attestation`, `GET /contribute/my-submissions`. |

Contributor-submitted senses always land with `review_status="pending"` and are invisible in public search until approved via `PATCH /admin/review/sense/{id}`.

## Vitality Score

`compute_vitality(senses, current_year=2026, zipf=None)` in `living_lexicon/vitality.py`:

- **V = 0.4·S + 0.4·D + 0.2·A**
- **S** (stability) — evidence grade weighted by source authority tier: Tier 1 (OED, de Vaan) = 1.0 weight, Tier 4 (community) = 0.25 weight. Minus semantic change diversity.
- **D** (drift score) — structural proxy: `semantic_change_type` diversity + year span; will migrate to cosine similarity once pgvector embeddings are populated
- **A** (attestation recency) — when `zipf` (wordfreq Zipf score, 1–7) is supplied: `A = 0.6·A_raw + 0.4·(zipf/7.0)`

`VitalityBreakdown` dataclass carries `frequency_zipf: float | None` and `authority_weighted: bool = True`.

`_tier_weight(source_slug)` is cached via `@lru_cache` — safe because `sources_catalog.ALL_SOURCES` is a static list.

## Semantic Relation Network

`word_relations` table: directed edges between words with `relation_type` in:
`synonym | antonym | hypernym | hyponym | meronym | holonym | cognate | derived_from | root_of | calque_of | doublet_of`

Key educator endpoint: `GET /pg/word/{word}/family` — BFS traversal via `derived_from`/`root_of` edges (depth 3, limit 50). Shows all words in the same derivational family.

## Morphological Decomposition

`morphemes` table: structured prefix/root/suffix decomposition per word.

Research endpoint: `GET /pg/morpheme/{morpheme}/words?role=root` — all words sharing a root morpheme across the corpus. Enables publishable corpus queries ("all words with Latin suffix *-tion* attested before 1600").

## Etymology Path

`living_lexicon/etymology_path.py` — pure function, no DB access:

```python
from living_lexicon.etymology_path import build_etymology_path
path = build_etymology_path(word_row, senses, relations)
# path.steps = [EtymologyStep(form, language, era_or_period, meaning, reconstruction_level)]
```

Steps are ordered oldest → newest: proto-language ancestors → etymology root → historical era senses → modern form. Exposed at `GET /pg/word/{word}/etymology-path`.

## New Fields on Sense

| Field | Values | Purpose |
|---|---|---|
| `reconstruction_level` | `attested \| reconstructed \| disputed \| folk_etymology` | Distinguishes PIE reconstructions (*) from attested forms — required for academic citation |
| `learner_level` | `beginner \| intermediate \| advanced \| research` | Filter senses for educational contexts via `?learner_level=beginner` |

## Citation Export

`living_lexicon/citation_formatter.py` — pure functions, no DB access, safe to import anywhere:

```python
from living_lexicon.citation_formatter import to_bibtex, to_apa, to_mla, to_chicago

bibtex = to_bibtex(sense, access_url="http://localhost:8000")
```

Citation key format: `living_lexicon_{word}_{source_slug}_{first_attested_year}`
Author resolved from `ingestor.sources_catalog.ALL_SOURCES` by `source_slug`.

## Dataset Snapshots

`POST /pg/snapshots` (admin) serializes all `words`, `senses`, and `attestations` rows to JSONB in the `dataset_snapshots` table. Use `GET /pg/snapshots/{tag}/export?format=jsonl|csv` for a `StreamingResponse` download. Snapshots are immutable once created — tag must be unique.

## Key Conventions

- `clean_str` / `safe_int` / `safe_float` live in `ingestor/utils.py` — import from there, never redefine locally.
- `WordHistorian` returns pure dataclasses (`WordContext`, `DriftExplanation`, etc.) — never raw dicts.
- `InMemoryStore` constructor keys words by **lowercase** name. `get_word()` lowercases its argument.
- Provider extras: `neo4j` guards `Neo4jStore`; `ollama` guards `OllamaProvider`. Both are `None` on minimal installs. **Import both lazily** (inside function bodies in `api/deps.py`) to prevent import-time failures on minimal installs.
- LLM era selection: `prompts.py` caps era blocks at 4 eras (first + last always kept, remainder by authority tier) to limit token usage with Ollama.
- `DatasetSnapshot.snapshot_data` uses `_PortableJSONB` — a `TypeDecorator` that stores JSON as text on SQLite and as native JSONB on PostgreSQL. Do not use `JSONB` directly in models.
- When adding a new route that uses a new CRUD function, also patch it in `tests/conftest.py`.
