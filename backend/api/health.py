"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from backend.services.database import fetch_scalar

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    """Basic health check — verifies DB connectivity."""
    try:
        result = fetch_scalar("SELECT 1")
        db_ok = result == 1
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
    }
