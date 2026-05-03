"""API-specific configuration.

Reads shared DB config from pipeline.config and adds API-layer
settings (pagination limits, CORS origins, rate limits).
"""

from __future__ import annotations

import os
from pathlib import Path

from pipeline.config import DB_CONFIG, US_BBOX  # noqa: F401 — re-exported

# ── Project root ────────────────────────────────────────────
# Anchor all data paths to the repo root so the server works
# regardless of which directory uvicorn is launched from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Database ────────────────────────────────────────────────
# Allow direct DATABASE_URL override (e.g. managed Postgres / Fly.io).
# Falls back to MR_DB_* vars from pipeline.config.
DATABASE_URL = os.environ.get("DATABASE_URL") or (
    f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}"
    f"/{DB_CONFIG['dbname']}"
)

# ── Pagination ──────────────────────────────────────────────
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 5_000

# ── CORS ────────────────────────────────────────────────────
# Comma-separated list of allowed origins. Defaults to local dev
# servers; in production set MR_CORS_ORIGINS to your Vercel URL.
_default_cors = (
    "http://localhost:3000,http://localhost:5173,"
    "http://127.0.0.1:3000,http://127.0.0.1:5173"
)
CORS_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get("MR_CORS_ORIGINS", _default_cors).split(",")
    if o.strip()
]

# ── Bounding box limits ─────────────────────────────────────
# Max area (degrees²) a single request can query.
# 10° × 10° ≈ 100 deg² covers most regional queries.
MAX_BBOX_AREA_DEG2 = 100.0

# ── API metadata ────────────────────────────────────────────
API_TITLE = "Marine Risk Mapping API"
API_VERSION = "0.1.0"
API_DESCRIPTION = (
    "REST API for whale–vessel collision risk data, species "
    "distribution, vessel traffic, and photo classification."
)
