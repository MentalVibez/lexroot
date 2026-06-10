#!/usr/bin/env python3
"""Create the Render MVP services for PensiveApe.

This script intentionally reads secrets from environment variables only.
It creates missing services and custom domains, then triggers deploys.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


API_BASE = "https://api.render.com/v1"
DEFAULT_OWNER_ID = "tea-d8koipn7f7vs73e30o7g"
DEFAULT_REPO = "https://github.com/MentalVibez/lexroot"
DEFAULT_BRANCH = "feat/linguistic-quality-layer"


def normalize_postgres_url(url: str, async_driver: bool) -> str:
    parts = urllib.parse.urlsplit(url)
    scheme = "postgresql" if parts.scheme == "postgres" else parts.scheme
    if async_driver and scheme in {"postgresql", "postgresql+psycopg2"}:
        scheme = "postgresql+asyncpg"
    if not async_driver and scheme == "postgresql+asyncpg":
        scheme = "postgresql"
    return urllib.parse.urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))


def password_from_url(url: str) -> str:
    password = urllib.parse.urlsplit(url).password
    return urllib.parse.unquote(password) if password else ""


class RenderClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def request(self, method: str, path: str, body: dict | None = None) -> object:
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(
            f"{API_BASE}{path}",
            data=data,
            method=method,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                raw = res.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            details = exc.read().decode(errors="replace")
            raise RuntimeError(f"Render API {method} {path} failed: HTTP {exc.code}: {details}") from exc

    def list_services(self, owner_id: str) -> list[dict]:
        services: list[dict] = []
        cursor = ""
        while True:
            query = urllib.parse.urlencode({"ownerId": owner_id, "limit": "100", **({"cursor": cursor} if cursor else {})})
            page = self.request("GET", f"/services?{query}")
            if not isinstance(page, list):
                raise RuntimeError("Unexpected Render service list response")
            for item in page:
                if "service" in item:
                    services.append(item["service"])
            next_cursor = page[-1].get("cursor") if page else None
            if not next_cursor:
                return services
            cursor = next_cursor

    def find_service(self, owner_id: str, name: str) -> dict | None:
        return next((svc for svc in self.list_services(owner_id) if svc.get("name") == name), None)

    def create_service(self, payload: dict) -> dict:
        created = self.request("POST", "/services", payload)
        if not isinstance(created, dict):
            raise RuntimeError("Unexpected Render service create response")
        return created.get("service", created)

    def ensure_domain(self, service_id: str, domain: str) -> None:
        encoded = urllib.parse.urlencode({"name": domain})
        existing = self.request("GET", f"/services/{service_id}/custom-domains?{encoded}")
        if isinstance(existing, list) and existing:
            print(f"domain exists: {domain}")
            return
        try:
            self.request("POST", f"/services/{service_id}/custom-domains", {"name": domain})
            print(f"domain added: {domain}")
        except RuntimeError as exc:
            if "HTTP 409" in str(exc):
                print(f"domain already claimed: {domain}")
                return
            raise

    def trigger_deploy(self, service_id: str) -> None:
        self.request("POST", f"/services/{service_id}/deploys", {"clearCache": "do_not_clear"})


def service_id(service: dict) -> str:
    sid = service.get("id")
    if not sid:
        raise RuntimeError(f"Render service response did not include an id: {service}")
    return sid


def service_url(service: dict) -> str:
    return service.get("serviceDetails", {}).get("url") or service.get("dashboardUrl") or service.get("id", "unknown")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create PensiveApe Render services from the current GitHub branch.")
    parser.add_argument("--owner-id", default=os.getenv("RENDER_OWNER_ID", DEFAULT_OWNER_ID))
    parser.add_argument("--repo", default=os.getenv("RENDER_REPO", DEFAULT_REPO))
    parser.add_argument("--branch", default=os.getenv("RENDER_BRANCH", DEFAULT_BRANCH))
    parser.add_argument("--api-name", default="pensiveape-api")
    parser.add_argument("--web-name", default="pensiveape-web")
    args = parser.parse_args()

    api_key = os.getenv("RENDER_API_KEY")
    database_url = os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not api_key:
        print("Missing RENDER_API_KEY.", file=sys.stderr)
        return 2
    if not database_url:
        print("Missing SUPABASE_DATABASE_URL or DATABASE_URL.", file=sys.stderr)
        return 2

    async_url = normalize_postgres_url(database_url, async_driver=True)
    sync_url = normalize_postgres_url(database_url, async_driver=False)
    db_password = password_from_url(database_url)

    client = RenderClient(api_key)

    api_service = client.find_service(args.owner_id, args.api_name)
    if api_service:
        print(f"api service exists: {args.api_name} ({service_id(api_service)})")
    else:
        api_service = client.create_service(
            {
                "type": "web_service",
                "name": args.api_name,
                "ownerId": args.owner_id,
                "repo": args.repo,
                "branch": args.branch,
                "autoDeploy": "yes",
                "envVars": [
                    {"key": "APP_ENV", "value": "production"},
                    {"key": "CORS_ORIGINS", "value": "https://pensiveape.com,https://www.pensiveape.com"},
                    {"key": "ENABLE_NEO4J", "value": "false"},
                    {"key": "ENABLE_OLLAMA", "value": "false"},
                    {"key": "ENABLE_WRITE_ENDPOINTS", "value": "false"},
                    {"key": "REQUIRE_API_KEY", "value": "false"},
                    {"key": "AUTO_CREATE_TABLES", "value": "false"},
                    {"key": "ADMIN_API_TOKEN", "value": secrets.token_urlsafe(32)},
                    {"key": "DATABASE_URL", "value": database_url},
                    {"key": "POSTGRES_URL", "value": async_url},
                    {"key": "POSTGRES_SYNC_URL", "value": sync_url},
                    {"key": "POSTGRES_PASSWORD", "value": db_password},
                ],
                "serviceDetails": {
                    "runtime": "docker",
                    "plan": "free",
                    "region": "oregon",
                    "healthCheckPath": "/health",
                    "envSpecificDetails": {
                        "dockerContext": ".",
                        "dockerfilePath": "./Dockerfile",
                    },
                },
            }
        )
        print(f"api service created: {args.api_name} ({service_id(api_service)})")
        time.sleep(2)

    web_service = client.find_service(args.owner_id, args.web_name)
    if web_service:
        print(f"web service exists: {args.web_name} ({service_id(web_service)})")
    else:
        web_service = client.create_service(
            {
                "type": "static_site",
                "name": args.web_name,
                "ownerId": args.owner_id,
                "repo": args.repo,
                "branch": args.branch,
                "autoDeploy": "yes",
                "serviceDetails": {
                    "buildCommand": "",
                    "publishPath": "frontend",
                    "routes": [{"type": "rewrite", "source": "/*", "destination": "/index.html"}],
                },
            }
        )
        print(f"web service created: {args.web_name} ({service_id(web_service)})")
        time.sleep(2)

    api_id = service_id(api_service)
    web_id = service_id(web_service)
    client.ensure_domain(api_id, "api.pensiveape.com")
    client.ensure_domain(web_id, "pensiveape.com")
    client.ensure_domain(web_id, "www.pensiveape.com")

    client.trigger_deploy(api_id)
    client.trigger_deploy(web_id)

    print("\nNext:")
    print("1. In Render, copy the DNS records shown for each custom domain.")
    print("2. Add those records at the DNS host for pensiveape.com.")
    print("3. Verify https://api.pensiveape.com/health and https://pensiveape.com after DNS propagates.")
    print(f"API service: {service_url(api_service)}")
    print(f"Web service: {service_url(web_service)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
