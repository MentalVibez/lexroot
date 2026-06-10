# Render Deployment: PensiveApe MVP

This project can deploy to Render for a lower-cost MVP than the AWS ECS stack.

## Architecture

- Static site: `pensiveape-web`
  - Serves `frontend/`
  - Custom domains: `pensiveape.com`, `www.pensiveape.com`
- API: `pensiveape-api`
  - Docker web service using `Dockerfile`
  - Custom domain: `api.pensiveape.com`
  - Runs `alembic upgrade head` before deploy
- Database: `living-lexicon-db`
  - Render Postgres `basic-256mb`
  - Persistent paid database for growing curated word data

Expected baseline cost is about $13/month: $7 web service + $6 Postgres.

## First Deploy

1. Push a branch containing `render.yaml`.
2. In Render, create a new Blueprint from the GitHub repo and branch.
3. Confirm the Blueprint provisions:
   - `pensiveape-api`
   - `pensiveape-web`
   - `living-lexicon-db`
4. Add the DNS records Render provides for:
   - `pensiveape.com`
   - `www.pensiveape.com`
   - `api.pensiveape.com`
5. Wait for TLS certificates to become active.

## Production Environment

The Blueprint sets:

- `APP_ENV=production`
- `CORS_ORIGINS=https://pensiveape.com,https://www.pensiveape.com`
- `ENABLE_NEO4J=false`
- `ENABLE_OLLAMA=false`
- `ENABLE_WRITE_ENDPOINTS=false`
- `REQUIRE_API_KEY=false`
- `AUTO_CREATE_TABLES=false`

Render injects the database connection string through `DATABASE_URL`,
`POSTGRES_URL`, and `POSTGRES_SYNC_URL`. The app normalizes Render's standard
Postgres URL into the async SQLAlchemy URL required by `asyncpg`.

## Post-Deploy Checks

```bash
curl https://api.pensiveape.com/health
curl https://api.pensiveape.com/pg/word/awful
curl "https://api.pensiveape.com/pg/words/search?q=nice&limit=5"
```

Verify in the browser:

- `https://pensiveape.com`
- `https://www.pensiveape.com`
- Search for `awful`, `nice`, `lord`, `silly`, `prevent`, and `charity`.
- Text Help flags `prevented` in the sample sentence.

## Seeding Data

The MVP fallback words keep the public site useful even before the database is
seeded. For persistent growth, import curated data after the first deploy using
a trusted machine or Render shell with the external Render Postgres URL.

Recommended first seed path:

```bash
POSTGRES_SYNC_URL="<render external postgres url>" python3 -m ingestor.words_csv_importer
POSTGRES_SYNC_URL="<render external postgres url>" python3 -m ingestor.senses_importer
POSTGRES_SYNC_URL="<render external postgres url>" python3 -m ingestor.word_relations_importer
```

Keep write/admin endpoints disabled until admin authentication and workflows
are ready for production use.
