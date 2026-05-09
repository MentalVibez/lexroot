from __future__ import annotations

import logging
import logging.config
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.middleware import configure_middleware
from api.routes import admin, ai, eras, health, pg_words, sources, words
from living_lexicon.config import LexiconConfig


def _configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "format": '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
                }
            },
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"handlers": ["stdout"], "level": level},
        }
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    LexiconConfig().validate_security()

    if os.getenv("AUTO_CREATE_TABLES", "false").lower() == "true":
        from db.database import engine
        from db.database import Base
        import db.models  # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    yield


app = FastAPI(
    title="The Living Lexicon",
    description="Etymology framework — historical word context and semantic drift explorer",
    version="0.1.0",
    lifespan=lifespan,
)

_cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

configure_middleware(app)

app.include_router(health.router)
app.include_router(words.router)
app.include_router(pg_words.router)
app.include_router(ai.router)
app.include_router(eras.router)
app.include_router(sources.router)
app.include_router(admin.router)


# Static frontend must be mounted last so API routes win first.
_frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
