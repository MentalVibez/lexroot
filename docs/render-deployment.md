# Render Deployment: PensiveApe MVP

This project can deploy to Render for a lower-cost MVP than the AWS ECS stack.

## Architecture

- Static site: `pensiveape-web`
  - Serves `frontend/`
  - Custom domains: `pensiveape.com`, `www.pensiveape.com`
- API: `pensiveape-api`
  - Docker web service using `Dockerfile`
  - Custom domain: `api.pensiveape.com`
  - Free tier does not support Render `preDeployCommand`
- Database: `living-lexicon-db`
  - Render Postgres `free` for initial validation
  - Upgrade to `basic-256mb` before treating the word database as durable

The current Blueprint is set to Render's free tier for initial launch validation.
Upgrade the API to `starter` and Postgres to `basic-256mb` when you are ready
for a durable public MVP database.

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

Because the free web service tier does not support `preDeployCommand`, Alembic
migrations are not run automatically in this free Blueprint. The MVP fallback
words keep the public API useful until migrations and imports are run manually
or the API is upgraded to a paid plan.

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
seeded. Free Postgres is suitable only for launch validation. For persistent
growth, upgrade Postgres first, then import curated data using a trusted machine
or Render shell with the external Render Postgres URL.

Recommended first seed path:

```bash
POSTGRES_SYNC_URL="<render external postgres url>" alembic upgrade head
POSTGRES_SYNC_URL="<render external postgres url>" python3 -m ingestor.words_csv_importer
POSTGRES_SYNC_URL="<render external postgres url>" python3 -m ingestor.senses_importer
POSTGRES_SYNC_URL="<render external postgres url>" python3 -m ingestor.word_relations_importer
```

Keep write/admin endpoints disabled until admin authentication and workflows
are ready for production use.
