# lexroot

**Etymology API backbone** — a production-ready FastAPI service providing word lookup,
phonics classification, semantic drift, and historical context for 517,000+ English words
including medical and clinical terminology.

Built to be embedded in other projects: chatbots, AI agents, educational apps, and
language tools. Ships with a LangChain plugin for zero-friction AI integration.

---

## What's inside

| Layer | Technology | Purpose |
|---|---|---|
| API | FastAPI 0.111+ | HTTP layer, auth, rate limiting |
| Word index | PostgreSQL + SQLAlchemy 2.0 async | 517k words with definitions, phonemes, etymology |
| Etymology graph | Neo4j 5 | Word relationships, historical eras, source claims |
| LLM | Ollama (local) | Semantic drift, teaching cards, fact-checking |
| Migrations | Alembic | Schema versioning |
| Plugin | LangChain | Ready-made tools for AI agents |

---

## Word corpus

**517,977 unique words** built from six sources (highest priority first):

| Source | Words | What's included |
|---|---|---|
| Etymology seed databases (v1+v2) | 138 | Hand-curated with full etymology |
| Collins Scrabble Words (2019) | ~279k | Full definitions |
| Primary lexicon | ~3k | Core vocabulary |
| dwyl/english-words | ~370k | Broad coverage |
| Medical supplement | ~59k | ICD-10, DSM-5, clinical terminology, acronyms (ADHD, MRI, CBT…) |

Each word stores: `definition`, `phonemes`, `etymology_root`, `origin_language`,
`language_family`, `historical_context`, and `semantic_drift_history` (JSONB).

---

## Quick start

### 1. Configure

```bash
cp .env.example .env
# Edit .env — set strong passwords for POSTGRES_PASSWORD and NEO4J_PASSWORD
```

### 2. Start services

```bash
docker-compose up -d
```

All services (PostgreSQL, Neo4j, Ollama, API) are localhost-bound by default.

### 3. Apply database migrations

```bash
POSTGRES_URL=postgresql+asyncpg://lexicon:<password>@localhost:5432/living_lexicon \
  alembic upgrade head
```

### 4. Load the word corpus

```bash
# Generate the master lexicon (downloads dwyl word list ~10 MB)
python3 -m ingestor.words_merge_importer

# Generate medical supplement
python3 -m ingestor.medical_importer

# Re-merge to include medical terms
python3 -m ingestor.words_merge_importer --no-fetch

# Build one clean DB feed, including words and curated idioms.
# Entries still missing definitions are excluded by default.
python3 -m ingestor.lexicon_build_importer

# Preview the import
python3 -m ingestor.words_csv_importer \
  --path Words/build/lexicon_import.csv \
  --dry-run

# Generate a data quality report
python3 -m ingestor.data_quality_validator
# Report includes definition source/license counts and rejected-entry review data.

# Import into PostgreSQL (~5 min for 517k+ entries)
python3 -m ingestor.words_csv_importer \
  --path Words/build/lexicon_import.csv \
  --batch-size 2000
```

### 5. Build etymology data (optional, offline ~15 s)

```bash
python3 -m ingestor.etymology_pipeline --skip-wiktionary
# Full pass with Wiktionary phonemes (requires internet, resumable):
python3 -m ingestor.etymology_pipeline

# Optional: import page-cited Shipley root claims from Words/sources/shipley_roots.csv
python3 -m ingestor.shipley_importer --dry-run

# Optional: import historically scoped senses and dated attestations
python3 -m ingestor.senses_importer --dry-run
```

### 6. Access the API

```
http://localhost:8000/docs    ← interactive Swagger UI
http://localhost:8000/health  ← readiness probe
```

---

## API reference

### Word index (PostgreSQL — fast, no graph required)

```bash
# Look up a word
GET /pg/word/{word}

# Paginated list
GET /pg/words?offset=0&limit=50
# → { "items": [...], "total": 517977, "offset": 0, "limit": 50 }

# Prefix search
GET /pg/words/search?q=char&limit=20

# Historical senses and attestations
GET /pg/word/{word}/senses
GET /pg/sense/{sense_id}
GET /pg/sense/{sense_id}/attestations

# Scholarly quality fields on senses/attestations include:
# evidence_grade, confidence_reason, citation, page, entry_headword, review_status

# Upsert (requires admin token)
PUT /pg/word
Authorization: Bearer <ADMIN_API_TOKEN>
{ "word": "Charity", "definition": "...", "phonemes": "/ˈtʃær.ɪ.ti/",
  "origin_language": "Latin", "language_family": "Indo-European (Italic)" }
```

### Etymology & context (Neo4j — rich relationships)

```bash
GET /word/{word}                    # Full word context
GET /word/{word}/etymology-claims   # Source-attributed etymology evidence
GET /word/{word}/retrieval-bundle   # Complete context + claims + timeline for AI use
GET /word/{word}/tree               # Root tree
GET /word/{word}/cognates           # Related words sharing the same root
GET /search?q={query}&limit=10      # Full-text search
```

### Historical eras

```bash
GET /word/{word}/era-timeline        # Word meaning across 7 historical eras
GET /word/{word}/era/{era_name}      # Meaning in a specific era
GET /era/by-year/{year}              # Which era a year falls in
GET /era/{era_name}/words            # All words documented in an era
```

### AI features (Ollama)

```bash
GET /word/{word}/drift?context=legal      # Semantic drift explanation
GET /word/{word}/teaching-card?level=k3   # Classroom-ready teaching card
POST /word/{word}/fact-check              # Validate an AI response for accuracy
  { "answer": "...", "strict": true }
GET /word/{word}/word-detective           # Phonics rule classification
```

Word Detective can be strengthened with curated spelling-history evidence in
`Words/sources/spelling_history.csv`. See `docs/word_detective_quality.md`.

### Sources

```bash
GET /sources                      # All etymology sources with authority tiers
GET /sources/{slug}               # Source details
GET /word/{word}/sources          # Sources contributing to a word's etymology
```

### Health & admin

```bash
GET /health                       # Readiness: checks PostgreSQL, Neo4j, Ollama
POST /ingest                      # Ingest a new word into the graph (admin only)
```

---

## Security

Write endpoints are **disabled by default**. Enable them only when needed:

```bash
ENABLE_WRITE_ENDPOINTS=true
ADMIN_API_TOKEN=<strong-random-token>
```

For public deployments, set `APP_ENV=production`. The app will refuse to start if:
- `POSTGRES_PASSWORD` or `NEO4J_PASSWORD` is a known-weak value
- `CORS_ORIGINS=*` (must list explicit origins)
- Write endpoints are enabled without an `ADMIN_API_TOKEN`

Optional read-layer protection:

```bash
REQUIRE_API_KEY=true
PUBLIC_API_KEY=<strong-random-key>     # clients send as X-API-Key header
RATE_LIMIT_PER_MINUTE=120
```

See [SECURITY.md](SECURITY.md) for the full deployment checklist.

---

## LangChain integration

```python
from langchain_plugin import LexiconPlugin

plugin = LexiconPlugin(
    base_url="http://localhost:8000",
    api_key="your-public-key",   # optional
)
tools = plugin.get_tools()
# WordLookupTool, SemanticDriftTool, EraTimelineTool, SearchTool, GuardrailsTool
```

Use as tools in any LangChain agent:

```python
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI

agent = create_openai_tools_agent(ChatOpenAI(), tools, prompt)
result = AgentExecutor(agent=agent, tools=tools).invoke(
    {"input": "What is the Latin root of 'charity' and how has its meaning changed?"}
)
```

---

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests (no running database required)
pytest

# Run only the HTTP endpoint tests
pytest tests/test_pg_words.py -v
```

Tests use an in-memory SQLite database — no PostgreSQL or Neo4j needed.

---

## Project structure

```
api/              FastAPI routes, middleware, schemas, security
  routes/
    pg_words.py   PostgreSQL word index endpoints (/pg/*)
    words.py      Neo4j etymology endpoints
    ai.py         Semantic drift, teaching cards, fact-check
    eras.py       Historical era endpoints
    sources.py    Etymology source endpoints
    health.py     Readiness probe
db/               SQLAlchemy models, CRUD, Alembic migrations
alembic/          Schema migration versions
ingestor/         Data pipeline scripts
  words_merge_importer.py     Build master lexicon from all sources
  medical_importer.py         ICD-10 + DSM-5 + clinical vocabulary
  etymology_pipeline.py       Enrich with etymwn, Collins hints, Wiktionary
  lexicon_build_importer.py   Build one clean word/idiom import CSV
  data_quality_validator.py   Report missing definitions, weak sources, era issues
  words_csv_importer.py       Bulk-load CSV into PostgreSQL
  etymology_agents/           Three-agent etymology enrichment system
living_lexicon/   Core SDK (word context, drift, eras, prompts)
langchain_plugin/ Ready-made LangChain tools
Words/            Data directory (large files excluded from git — see readme.txt)
tests/            HTTP endpoint tests
```

---

## Configuration reference

Copy `.env.example` to `.env`. Key variables:

| Variable | Default | Notes |
|---|---|---|
| `APP_ENV` | `development` | Set `production` to enable security guards |
| `POSTGRES_URL` | — | asyncpg connection string |
| `NEO4J_URI` | `bolt://localhost:7687` | |
| `OLLAMA_MODEL` | `llama3` | Any model pulled into Ollama |
| `ENABLE_WRITE_ENDPOINTS` | `false` | Set `true` + `ADMIN_API_TOKEN` to unlock |
| `CORS_ORIGINS` | `*` | Must be explicit origins in production |
| `RATE_LIMIT_PER_MINUTE` | `120` | Per-IP; `0` disables |

Full list with documentation: [`.env.example`](.env.example)
