# The Living Lexicon

**Programmable Historical Semantic Intelligence** — a production-ready FastAPI service
for querying how words changed meaning across time. Built for PhD linguists who need
citable evidence, educators who need step-by-step etymology paths, and developers who
need an embeddable historical word API.

Sits between three existing markets without competing in any:
- Dictionary apps (static, consumer, not programmable)
- Corpus linguistics tools (academic, expensive, not developer-friendly)
- Brand monitoring tools (real-time frequency, no historical depth)

Ships with a LangChain plugin for zero-friction AI agent integration.

---

## What's inside

| Layer | Technology | Purpose |
|---|---|---|
| API | FastAPI 0.111+ | HTTP layer, auth, rate limiting |
| Relational store | PostgreSQL + SQLAlchemy 2.0 async | Words, senses, attestations, relations, morphemes |
| Graph store | Neo4j 5 | Etymological trees, cognates, cross-word relationships |
| Scoring | `living_lexicon/vitality.py` | Authority-weighted vitality score (V = 0.4·S + 0.4·D + 0.2·A) |
| LLM | Ollama (local) | Semantic drift, teaching cards, fact-checking |
| Migrations | Alembic | 13 versioned migrations (001–013) |
| Plugin | LangChain | Ready-made tools for AI agents |
| SDK | `living_lexicon/` | Pure Python, pip-installable, zero DB dependencies |

---

## Quick start

### 1. Configure

```bash
cp .env.example .env
# Set POSTGRES_PASSWORD, NEO4J_PASSWORD, ADMIN_API_TOKEN
```

### 2. Start services and API

```bash
make dev
# Starts: postgres, neo4j, ollama (detached), then the API (foreground)
```

### 3. Apply migrations

```bash
make migrate
# Runs: alembic upgrade head  (migrations 001–013)
```

### 4. Load corpus data

```bash
make import-gcide       # Webster's 1913 (~40k words) — requires Words/gcide-0.54.zip
make import-frequency   # wordfreq Zipf scores → words table
make import-senses      # curated senses + attestations from Words/sources/senses.csv
make import-morphemes   # morpheme decompositions from Words/morphemes.csv (author first)
make sync-neo4j         # sync PostgreSQL words/senses → Neo4j graph
```

### 5. Verify

```
http://localhost:8000/docs    ← Swagger UI (all endpoints)
http://localhost:8000/health  ← readiness probe
```

---

## All make targets

```bash
make dev              # Start Docker services + app
make test             # Fast suite — no Neo4j/Ollama/PostgreSQL required (39 tests)
make test-all         # pytest -v across all testpaths
make migrate          # alembic upgrade head
make import-senses    # python -m ingestor.senses_importer
make import-gcide     # Webster's 1913 from Words/gcide-0.54.zip
make import-frequency # wordfreq Zipf → words.wordfreq_zipf
make import-morphemes # morpheme CSV → morphemes table
make sync-neo4j       # PostgreSQL → Neo4j graph
make make-snapshot    # Prints curl command for POST /pg/snapshots
make lint             # ruff check living_lexicon/ ingestor/ api/ langchain_plugin/
make typecheck        # mypy living_lexicon/
make help             # List all targets
```

---

## API reference

### Words (PostgreSQL — fast, no graph required)

```bash
GET  /pg/word/{word}                          # word record
GET  /pg/words?offset=0&limit=50              # paginated list → { items, total, offset, limit }
GET  /pg/words/search?q=char&limit=20         # prefix search
PUT  /pg/word                                 # upsert (admin token required)
```

### Senses and attestations

```bash
GET  /pg/word/{word}/senses                   # historical senses, ordered by first_attested_year
     ?learner_level=beginner                  # filter: beginner | intermediate | advanced | research
     ?reconstruction_level=attested           # filter: attested | reconstructed | disputed | folk_etymology
GET  /pg/sense/{sense_id}                     # single sense
GET  /pg/sense/{sense_id}/attestations        # dated quotation evidence
PUT  /pg/sense                                # upsert (admin)
POST /pg/attestation                          # add quotation (admin)
```

### Vitality and semantic drift

```bash
GET  /pg/word/{word}/vitality
# → { vitality_score, metrics: { stability, drift_velocity, attestation_recency,
#     status, sense_count, last_attested }, frequency_zipf, note }
# Stability is authority-weighted: Tier 1 sources (OED, de Vaan) count 4× more than Tier 4

GET  /pg/word/{word}/drift-trajectory
# → { word, trajectory: [{ era, change_type, definition_excerpt, evidence_grade }],
#     sequence, unique_change_types, spans_years }

POST /pg/drift/compare
# Body: { "words": ["prevent", "awful", "nice"], "era": "Middle English" }
# → per-word vitality + era senses — core endpoint for comparative historical semantics

GET  /pg/semantic-fields?domain=law&change_type=pejoration&era=Early+Modern+English&limit=50
# → senses that share domain/change_type/era — at least one filter required
```

### Etymology path (educator endpoint)

```bash
GET  /pg/word/{word}/etymology-path
# → ordered steps oldest → newest: proto-language ancestors → historical eras → modern form
# { word, steps: [{ form, language, era_or_period, meaning, reconstruction_level }],
#   origin_language, language_family, total_steps }
```

### Word relations

```bash
GET  /pg/word/{word}/relations?type=synonym   # relation types: synonym | antonym | hypernym |
                                              # hyponym | meronym | holonym | cognate |
                                              # derived_from | root_of | calque_of | doublet_of
GET  /pg/word/{word}/family                   # derivational family BFS via derived_from/root_of
     ?depth=3&limit=50                        # (up to depth 5, max 200 words)
POST /pg/word/relation                        # add relation edge (admin)
```

### Morpheme decomposition

```bash
GET  /pg/word/{word}/morphemes                # prefix/root/suffix breakdown
# → [{ morpheme, role, origin_language, gloss, position }]

GET  /pg/morpheme/{morpheme}/words?role=root  # all words sharing a morpheme
# Key research endpoint: all words with Latin suffix -tion attested before 1600
```

### Period accuracy checking

```bash
POST /pg/word/era-check
# Body: { "text": "He tried to prevent the attack.", "era_name": "Middle English" }
# → flags words whose meaning in that era differs from the modern definition
# { era_name, words_checked, flagged_count, flagged: [{ word, era_definition, modern_definition }] }
```

### Citation export (academic)

```bash
GET  /pg/sense/{sense_id}/cite?format=bibtex  # format: bibtex | apa | mla | chicago
GET  /pg/word/{word}/cite?format=bibtex       # all senses, multi-entry BibTeX block
# Citation key: living_lexicon_{word}_{source_slug}_{first_attested_year}
```

### Dataset snapshots (reproducible research)

```bash
POST /pg/snapshots                            # admin — serialize full corpus to JSONB
GET  /pg/snapshots                            # list all snapshots (no data)
GET  /pg/snapshots/{tag}                      # full snapshot record
GET  /pg/snapshots/{tag}/export?format=jsonl  # StreamingResponse download (jsonl | csv)
```

### Frequency trending

```bash
GET  /pg/words/trending?direction=rising&min_zipf=4.0&limit=50
# direction: rising | declining — ranked by vitality score
```

### Contributor workflow

```bash
POST /contribute/sense                        # propose a sense (contributor token)
POST /contribute/attestation                  # propose a quotation (contributor token)
GET  /contribute/my-submissions?status=pending # track your submissions

GET  /admin/review/pending?word=awful         # list pending contributions (admin)
PATCH /admin/review/sense/{sense_id}          # approve or reject (admin)
# Body: { "action": "approve", "reviewer_notes": "..." }
```

### Etymology graph (Neo4j)

```bash
GET /word/{word}                    # full word context
GET /word/{word}/etymology-claims   # source-attributed etymology evidence
GET /word/{word}/retrieval-bundle   # complete context + claims + timeline for AI
GET /word/{word}/tree               # root tree
GET /word/{word}/cognates           # related words sharing the same root
GET /search?q={query}&limit=10      # full-text search
GET /word/{word}/era-timeline       # word meaning across historical eras
GET /era/by-year/{year}             # which era a year falls in
GET /sources                        # all etymology sources with authority tiers
```

### AI features (Ollama)

```bash
GET  /word/{word}/drift?context=legal       # semantic drift explanation
GET  /word/{word}/teaching-card?level=k3   # classroom-ready teaching card
POST /word/{word}/fact-check               # validate an AI response for accuracy
GET  /word/{word}/word-detective           # phonics rule classification
```

---

## Access control

Two token tiers — both passed as `Authorization: Bearer <token>`:

| Token | Env var | Controls |
|---|---|---|
| **Admin** | `ADMIN_API_TOKEN` | PUT /pg/word, PUT /pg/sense, POST /pg/attestation, POST /pg/snapshots, POST /pg/word/relation, GET+PATCH /admin/review/\* — also requires `ENABLE_WRITE_ENDPOINTS=true` |
| **Contributor** | `CONTRIBUTOR_API_TOKEN` | POST /contribute/sense, POST /contribute/attestation, GET /contribute/my-submissions |

Contributor senses always land with `review_status="pending"` and are invisible in public search until approved by an admin. Contributor identity is stored as `sha256(token:word)[:16]` — traceable but the raw token is never persisted.

Write endpoints return **404** (not 401) when `ENABLE_WRITE_ENDPOINTS=false`, so their existence is not revealed to unauthenticated callers.

---

## Vitality score

`compute_vitality(senses, current_year=2026, zipf=None)` in `living_lexicon/vitality.py`:

```
V = 0.4·S + 0.4·D + 0.2·A
```

| Component | What it measures |
|---|---|
| **S** (stability) | Evidence grade × source authority tier. Tier 1 sources (OED, de Vaan, Beekes) weight 1.0; Tier 4 (community) 0.25. Minus semantic change type diversity. |
| **D** (drift velocity) | Change-type breadth + proportion of senses with documented drift + year span (normalized to 1000 years). |
| **A** (attestation recency) | Harmonic decay from `last_attested_year`. When `wordfreq_zipf` is present: `A = 0.6·A_raw + 0.4·(zipf/7)`. |

Status labels: `highly_stable` | `highly_evolutionary` | `active` | `established` | `declining` | `archaic`

---

## Testing

Tests run with **no external dependencies** — no PostgreSQL, Neo4j, or Ollama required.

```bash
make test        # 39 tests, ~0.15 s
make test-all    # all testpaths including importer and SDK tests
```

HTTP endpoint tests monkeypatch all `crud.*` functions with in-memory dict-backed fakes.
SDK tests use `InMemoryStore` and `StubLLMProvider` from `living_lexicon/testing.py`.

```python
# HTTP test pattern
async def test_vitality_shape(app_client, write_headers):
    await app_client.put("/pg/word", json={"word": "awful"}, headers=write_headers)
    resp = await app_client.get("/pg/word/awful/vitality")
    assert resp.status_code == 200
    assert 0.0 <= resp.json()["vitality_score"] <= 1.0

# SDK test pattern
from living_lexicon.testing import InMemoryStore, WordHistorianFactory
from tests.factories import WordSeedFactory, EraTimelineFactory

store = InMemoryStore(
    words=WordSeedFactory.build_keyed("prevent", root_meaning="to come before"),
    era_timelines=EraTimelineFactory.build_timeline("prevent", {
        "Middle English": "to come before",
        "Early Modern English": "to hinder",
    }),
)
h = WordHistorianFactory.build(store=store, llm_response="It originally meant X.")
```

**Never** import `Neo4jStore` or `OllamaProvider` in tests. **Never** use `aiosqlite`.
If you add a new CRUD function used by an endpoint, add a matching monkeypatch to `tests/conftest.py`.

---

## Project structure

```
the-living-lexicon/
├── living_lexicon/          # SDK — pip-installable, zero external dependencies
│   ├── core.py              # WordHistorian — single entry point
│   ├── vitality.py          # compute_vitality() — authority-weighted V score
│   ├── citation_formatter.py  # to_bibtex/to_apa/to_mla/to_chicago
│   ├── etymology_path.py    # build_etymology_path() — ordered step builder
│   ├── word_detective.py    # phonics rule classifier
│   ├── testing.py           # InMemoryStore, StubLLMProvider, WordHistorianFactory
│   └── providers/           # Neo4jStore (neo4j extra), OllamaProvider (ollama extra)
├── api/
│   ├── main.py              # app + router registration
│   ├── security.py          # require_admin_token(), require_contributor_token()
│   └── routes/
│       ├── pg_words.py      # /pg/word — CRUD, vitality, era-check, morphemes, etymology-path
│       ├── pg_senses.py     # /pg/sense, /pg/attestation (+ ?learner_level filter)
│       ├── relations.py     # /pg/word/{word}/relations, /family, POST /pg/word/relation
│       ├── semantic_fields.py  # /pg/semantic-fields, /pg/drift/compare, /drift-trajectory
│       ├── citations.py     # /pg/sense/{id}/cite, /pg/word/{word}/cite
│       ├── snapshots.py     # /pg/snapshots — create, list, export
│       ├── frequency.py     # /pg/words/trending
│       ├── contributions.py # /contribute/sense|attestation|my-submissions
│       └── admin.py         # /admin/review/pending, /admin/review/sense/{id}
├── db/
│   ├── models.py            # Word, Sense, Attestation, DatasetSnapshot,
│   │                        # WordRelation, Morpheme ORM classes
│   └── crud.py              # all async CRUD functions
├── alembic/versions/        # 13 migrations (001–013)
├── ingestor/                # data import scripts
│   ├── base.py              # BaseImporter ABC + ImportResult
│   ├── gcide_importer.py    # Webster's 1913 (gcide-0.54.zip → PostgreSQL)
│   ├── senses_importer.py   # curated senses + attestations CSV
│   ├── shipley_importer.py  # Shipley root claims
│   ├── frequency_pg_importer.py  # wordfreq Zipf scores
│   ├── morphemes_importer.py     # morpheme CSV (prefix/root/suffix)
│   ├── neo4j_sync.py        # PostgreSQL → Neo4j sync
│   └── sources_catalog.py   # 62 sources with authority tiers 1–4
├── Words/sources/           # curated CSV data files (committed, versioned)
├── docs/                    # data quality standards and field guides
├── tests/
│   ├── conftest.py          # CRUD monkeypatches, SDK fixtures, app_client
│   ├── factories.py         # WordPayloadFactory, SensePayloadFactory, ...
│   ├── test_pg_words.py
│   ├── test_pg_senses.py
│   ├── test_semantic_fields.py
│   └── test_contributions.py
└── langchain_plugin/        # LangChain tool wrapper
```

---

## Configuration reference

| Variable | Default | Notes |
|---|---|---|
| `APP_ENV` | `development` | Set `production` to enable security guards |
| `DATABASE_URL` | — | psycopg2 connection string (for importers) |
| `POSTGRES_URL` | — | asyncpg connection string (for the API) |
| `NEO4J_URI` | `bolt://localhost:7687` | |
| `OLLAMA_MODEL` | `llama3` | Any model pulled into Ollama |
| `ENABLE_WRITE_ENDPOINTS` | `false` | Set `true` + `ADMIN_API_TOKEN` to unlock |
| `ADMIN_API_TOKEN` | — | Strong random token for admin endpoints |
| `CONTRIBUTOR_API_TOKEN` | — | Token for contributor submission endpoints |
| `CORS_ORIGINS` | `*` | Must be explicit origins in production |
| `RATE_LIMIT_PER_MINUTE` | `120` | Per-IP; `0` disables |
| `LOG_LEVEL` | `INFO` | JSON-structured stdout logging |
| `AUTO_CREATE_TABLES` | `false` | Create tables on startup (dev only; use migrations in prod) |

The app **refuses to start** in production if:
- `POSTGRES_PASSWORD` or `NEO4J_PASSWORD` is a known-weak value
- `CORS_ORIGINS=*`
- Write endpoints are enabled without `ADMIN_API_TOKEN`

---

## Source authority tiers

62 sources registered in `ingestor/sources_catalog.py`:

| Tier | Weight in vitality | Examples |
|---|---|---|
| 1 — Primary etymological | 1.0 | OED, MED, de Vaan, Beekes, Barnhart, Watkins PIE |
| 2 — Major historical dictionaries | 0.75 | Century Dictionary, Webster 1828, Skeat |
| 3 — Specialist references | 0.50 | Merriam-Webster, Collins, Shakespeare, KJV |
| 4 — Supplementary | 0.25 | Partridge slang, Grose, community sources |

---

## LangChain integration

```python
from langchain_plugin import LexiconPlugin

plugin = LexiconPlugin(base_url="http://localhost:8000", api_key="your-public-key")
tools = plugin.get_tools()
# WordLookupTool, SemanticDriftTool, EraTimelineTool, SearchTool, GuardrailsTool

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI

agent = create_openai_tools_agent(ChatOpenAI(), tools, prompt)
AgentExecutor(agent=agent, tools=tools).invoke(
    {"input": "What is the Latin root of 'charity' and how has its meaning changed?"}
)
```

---

## Known content gaps

These are data problems, not code problems. The API, tables, and importers are ready.

| Gap | What to do |
|---|---|
| `morphemes` table is empty | Author `Words/morphemes.csv` (columns: word, morpheme, role, origin_language, gloss, position, source_slug) then `make import-morphemes` |
| `word_relations` table is empty | Add edges via `POST /pg/word/relation` (admin) or write a bulk importer from WordNet/Wiktionary relation data |
| `learner_level` defaults to `intermediate` on all senses | Add `learner_level` column to `Words/sources/senses.csv` and re-run `make import-senses` |
| `reconstruction_level` defaults to `attested` | Tag PIE-reconstructed senses as `reconstructed` in the senses CSV |
| pgvector embeddings | Migration 007 adds the column; populate with any embedding model after `make import-senses` |
