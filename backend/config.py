"""API-specific configuration.

Reads shared DB config from pipeline.config and adds API-layer
settings (pagination limits, CORS origins, rate limits).
"""

from __future__ import annotations

from pipeline.config import DB_CONFIG, US_BBOX  # noqa: F401 — re-exported

# ── Database ────────────────────────────────────────────────
DATABASE_URL = (
    f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}"
    f"/{DB_CONFIG['dbname']}"
)

# ── Pagination ──────────────────────────────────────────────
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 5_000

# ── CORS ────────────────────────────────────────────────────
CORS_ORIGINS: list[str] = [
    "http://localhost:3000",  # Next.js dev
    "http://localhost:5173",  # Vite dev
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
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
