# Security Policy

## Supported Use

The Living Lexicon is designed to run locally by default. Public deployments should
set production environment variables, use strong secrets, and keep write paths
disabled unless explicitly needed.

## Deployment Checklist

- Set `APP_ENV=production`.
- Set a strong `NEO4J_PASSWORD`; do not use `lexicon_secret`.
- Keep Neo4j and Ollama ports bound to localhost or a private network.
- Leave `ENABLE_WRITE_ENDPOINTS=false` unless an admin ingest API is required.
- If write endpoints are enabled, set a strong `ADMIN_API_TOKEN` and send it as:
  `Authorization: Bearer <token>`.
- Put the API behind TLS and an authenticating reverse proxy before exposing it.
- For public reads, set `REQUIRE_API_KEY=true` and a strong `PUBLIC_API_KEY`.
- Tune `RATE_LIMIT_PER_MINUTE` for expected traffic.
- Run `python -m ingestor.migrate_schema` before serving traffic.

## Data Ingestion

All imported datasets must be treated as untrusted input.

- Prefer local files over automatic downloads.
- Download datasets only from known upstream projects.
- Keep checksums for large datasets when possible.
- Run importer `--dry-run` first and inspect counts/samples.
- Use conservative `--limit` values before running unlimited imports.
- Keep source/license metadata attached to imported claims.

## Runtime Protections

The API installs lightweight request protection:

- `X-Request-ID` response header for tracing.
- Basic security headers.
- Optional read API key enforcement.
- In-memory per-client rate limiting.

For multi-worker or multi-instance deployments, put a gateway/reverse proxy in
front of the app and enforce distributed rate limiting there.

## Reporting Issues

If you find a vulnerability, do not publish exploit details in a public issue.
Contact the project maintainer privately with reproduction steps and affected
configuration.
