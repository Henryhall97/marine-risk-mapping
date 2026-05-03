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
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.gzip import GZipMiddleware

from backend.api import (
    audio,
    auth,
    events,
    export,
    external_events,
    health,
    layers,
    macro,
    media,
    photo,
    risk,
    sightings,
    species,
    submissions,
    traffic,
    vessels,
    violations,
    zones,
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
    init_pool(min_conn=4, max_conn=50)
    yield
    close_pool()
    log.info("Shutdown complete")


# ── App ─────────────────────────────────────────────────────

# Rate limiter — keyed by client IP address.  Limits are
# applied per-endpoint via @limiter.limit() decorators.
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Gzip ────────────────────────────────────────────────────
# Compress responses ≥ 1 KB — large GeoJSON and risk payloads
# shrink 3-5× on the wire.

app.add_middleware(GZipMiddleware, minimum_size=1000)

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
app.include_router(zones.router, prefix=_API_PREFIX)
app.include_router(violations.router, prefix=_API_PREFIX)
app.include_router(export.router, prefix=_API_PREFIX)

# Auth, vessels, submissions & events (own prefix — /api/v1/auth, etc.)
app.include_router(auth.router)
app.include_router(vessels.router)
app.include_router(submissions.router)
app.include_router(events.router)
app.include_router(external_events.router)

# Media file serving
app.include_router(media.router, prefix=_API_PREFIX)

# Macro overview (coast-wide, no prefix — already has /api/v1/macro)
app.include_router(macro.router)


# ── Direct execution ────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
