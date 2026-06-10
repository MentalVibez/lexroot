# Render Deployment: PensiveApe MVP

This project can deploy to Render for app hosting and Supabase for durable
Postgres/Auth.

## Architecture

- Static site: `pensiveape-web`
  - Serves `frontend/`
  - Custom domains: `pensiveape.com`, `www.pensiveape.com`
- API: `pensiveape-api`
  - Docker web service using `Dockerfile`
  - Custom domain: `api.pensiveape.com`
  - Free tier does not support Render `preDeployCommand`
- Database: Supabase Postgres
  - Store the connection strings as secret env vars on `pensiveape-api`
  - Use Supabase Auth later for saved words, classrooms, and collections

The current Blueprint keeps Render on the free tier for initial launch
validation. Supabase provides the durable database layer.

## First Deploy

1. Push a branch containing `render.yaml`.
2. In Render, create a new Blueprint from the GitHub repo and branch.
3. Confirm the Blueprint provisions:
   - `pensiveape-api`
   - `pensiveape-web`
4. In Supabase, create a project and copy the Postgres connection string.
5. In Render, set these secret env vars on `pensiveape-api`:
   - `DATABASE_URL`
   - `POSTGRES_URL`
   - `POSTGRES_SYNC_URL`
   - `POSTGRES_PASSWORD`
6. Add the DNS records Render provides for:
   - `pensiveape.com`
   - `www.pensiveape.com`
   - `api.pensiveape.com`
7. Wait for TLS certificates to become active.

## Production Environment

The Blueprint sets:

- `APP_ENV=production`
- `CORS_ORIGINS=https://pensiveape.com,https://www.pensiveape.com`
- `ENABLE_NEO4J=false`
- `ENABLE_OLLAMA=false`
- `ENABLE_WRITE_ENDPOINTS=false`
- `REQUIRE_API_KEY=false`
- `AUTO_CREATE_TABLES=false`

Render expects the database connection strings to be set manually from Supabase.
The app normalizes Supabase/standard Postgres URLs into the async SQLAlchemy URL
required by `asyncpg`.

Because the free web service tier does not support `preDeployCommand`, Alembic
migrations are not run automatically in this free Blueprint. The MVP fallback
words keep the public API useful until migrations and imports are run manually.

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

The MVP fallback words keep the public site useful even before Supabase is
seeded. For persistent growth, run migrations and import curated data using a
trusted machine with the Supabase pooled or direct Postgres URL.

Recommended first seed path:

```bash
POSTGRES_SYNC_URL="<supabase postgres url>" alembic upgrade head
POSTGRES_SYNC_URL="<supabase postgres url>" python3 -m ingestor.words_csv_importer
POSTGRES_SYNC_URL="<supabase postgres url>" python3 -m ingestor.senses_importer
POSTGRES_SYNC_URL="<supabase postgres url>" python3 -m ingestor.word_relations_importer
```

Keep write/admin endpoints disabled until admin authentication and workflows
are ready for production use.
