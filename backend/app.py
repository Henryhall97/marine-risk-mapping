"""FastAPI application entry point.

Start the API server::

    uv run uvicorn backend.app:app --reload --port 8000

Or from project root::

    uv run python -m backend.app
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import (
    audio,
    health,
    layers,
    photo,
    risk,
    sightings,
    species,
    traffic,
)
from backend.config import (
    API_DESCRIPTION,
    API_TITLE,
    API_VERSION,
    CORS_ORIGINS,
)
from backend.services.database import close_pool, init_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-25s %(levelname)-7s %(message)s",
)
log = logging.getLogger(__name__)


# ── Lifespan ────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Startup / shutdown hooks.

    Creates the DB connection pool on startup, tears it down on
    shutdown.
    """
    log.info("Starting %s v%s", API_TITLE, API_VERSION)
    init_pool(min_conn=2, max_conn=10)
    yield
    close_pool()
    log.info("Shutdown complete")


# ── App ─────────────────────────────────────────────────────

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ──────────────────────────────────────────────────

# Health check at root level (/health)
app.include_router(health.router)

# Domain routers under /api/v1 prefix
_API_PREFIX = "/api/v1"
app.include_router(risk.router, prefix=_API_PREFIX)
app.include_router(species.router, prefix=_API_PREFIX)
app.include_router(traffic.router, prefix=_API_PREFIX)
app.include_router(layers.router, prefix=_API_PREFIX)
app.include_router(photo.router, prefix=_API_PREFIX)
app.include_router(audio.router, prefix=_API_PREFIX)
app.include_router(sightings.router, prefix=_API_PREFIX)


# ── Direct execution ────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
