import os
import secrets

from fastapi import HTTPException


def require_admin_token(authorization: str | None) -> None:
    if os.getenv("ENABLE_WRITE_ENDPOINTS", "false").lower() != "true":
        # 404 intentionally: don't reveal whether admin endpoints exist
        raise HTTPException(status_code=404, detail="Not found")

    token = os.getenv("ADMIN_API_TOKEN", "")
    if not token:
        raise HTTPException(status_code=500, detail="Write endpoints are misconfigured on the server")

    provided = (authorization or "").removeprefix("Bearer ").strip()
    if not secrets.compare_digest(provided.encode(), token.encode()):
        raise HTTPException(status_code=401, detail="Invalid admin token")
