from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter

from api.deps import get_historian

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


@router.get("/health")
async def health_check():
    """Readiness probe: verifies Neo4j, PostgreSQL, and Ollama are reachable."""
    neo4j_enabled = os.getenv("ENABLE_NEO4J", "true").lower() == "true"
    ollama_enabled = os.getenv("ENABLE_OLLAMA", "true").lower() == "true"

    if neo4j_enabled:
        historian = get_historian()
        neo4j_ok = historian._store.ping() if hasattr(historian._store, "ping") else True
        neo4j_status = "ready" if neo4j_ok else "error"
    else:
        neo4j_status = "disabled"

    if ollama_enabled:
        ollama_status = "unknown"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
                ollama_status = "ready" if resp.status_code == 200 else f"http_{resp.status_code}"
        except Exception as e:
            logger.warning("Ollama health check failed: %s", e)
            ollama_status = "unreachable"
    else:
        ollama_status = "disabled"

    pg_status = "unknown"
    try:
        from db.database import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        pg_status = "ready"
    except Exception as e:
        logger.warning("PostgreSQL health check failed: %s", e)
        pg_status = "unreachable"

    checks = {"neo4j": neo4j_status, "ollama": ollama_status, "postgres": pg_status}
    required_ok = pg_status == "ready" and (neo4j_status in {"ready", "disabled"}) and (ollama_status in {"ready", "disabled"})
    overall = "healthy" if required_ok else "degraded"

    return {
        **checks,
        "overall": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
