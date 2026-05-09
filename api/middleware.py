from __future__ import annotations

import logging
import os
import secrets
import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

PUBLIC_PATH_PREFIXES = ("/health", "/docs", "/redoc", "/openapi.json")

# Set TRUSTED_PROXY=true only when the app is behind a known reverse proxy
# (nginx, AWS ALB, etc.) that sets X-Forwarded-For reliably.
_TRUSTED_PROXY = os.getenv("TRUSTED_PROXY", "false").lower() == "true"


def _client_ip(request: Request) -> str:
    if _TRUSTED_PROXY:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def configure_middleware(app: FastAPI) -> None:
    """Install production-oriented HTTP middleware without external dependencies."""
    require_api_key = os.getenv("REQUIRE_API_KEY", "false").lower() == "true"
    rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
    buckets: dict[str, deque[float]] = defaultdict(deque)

    @app.middleware("http")
    async def security_and_rate_limit(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        path = request.url.path

        if require_api_key and not path.startswith(PUBLIC_PATH_PREFIXES):
            api_key = os.getenv("PUBLIC_API_KEY", "")
            if not api_key:
                return JSONResponse(
                    {"detail": "API key authentication is misconfigured"},
                    status_code=500,
                    headers={"X-Request-ID": request_id},
                )
            provided = request.headers.get("X-API-Key") or ""
            if not secrets.compare_digest(provided.encode(), api_key.encode()):
                logger.warning("Invalid API key from %s %s", _client_ip(request), path)
                return JSONResponse(
                    {"detail": "Invalid API key"},
                    status_code=401,
                    headers={"X-Request-ID": request_id},
                )

        client = _client_ip(request)
        now = time.monotonic()
        bucket = buckets[client]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if rate_limit_per_minute > 0 and len(bucket) >= rate_limit_per_minute:
            logger.warning("Rate limit hit for %s", client)
            return JSONResponse(
                {"detail": "Rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": "60", "X-Request-ID": request_id},
            )
        bucket.append(now)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response
