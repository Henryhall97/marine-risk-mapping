"""Database connection pool and query helpers.

Uses psycopg2 with a simple connection pool.  The pool is created
once at application startup (via FastAPI lifespan) and closed at
shutdown.

All query functions return lists of dicts (rows) to keep the
service layer independent of Pydantic models.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from psycopg2.extras import RealDictCursor
from psycopg2.pool import PoolError, ThreadedConnectionPool

from backend.config import DATABASE_URL

log = logging.getLogger(__name__)

# Module-level pool — initialised by init_pool(), closed by close_pool()
_pool: ThreadedConnectionPool | None = None

# Retry settings for transient pool exhaustion
_POOL_RETRY_ATTEMPTS = 5
_POOL_RETRY_BASE_DELAY = 0.05  # 50 ms, doubles each attempt


def init_pool(min_conn: int = 2, max_conn: int = 10) -> None:
    """Create the threaded connection pool."""
    global _pool  # noqa: PLW0603
    if _pool is not None:
        log.warning("Pool already initialised — skipping")
        return
    _pool = ThreadedConnectionPool(min_conn, max_conn, DATABASE_URL)
    log.info("DB pool created (%d–%d connections)", min_conn, max_conn)


def close_pool() -> None:
    """Close all connections in the pool."""
    global _pool  # noqa: PLW0603
    if _pool is not None:
        _pool.closeall()
        _pool = None
        log.info("DB pool closed")


@contextmanager
def get_conn() -> Generator:
    """Yield a connection from the pool, auto-return on exit.

    Retries with exponential back-off when the pool is transiently
    exhausted (e.g. many concurrent map-tile fetches).
    """
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_pool() first")

    conn = None
    for attempt in range(_POOL_RETRY_ATTEMPTS):
        try:
            conn = _pool.getconn()
            break
        except PoolError:
            if attempt == _POOL_RETRY_ATTEMPTS - 1:
                log.error(
                    "Connection pool exhausted after %d retries",
                    _POOL_RETRY_ATTEMPTS,
                )
                raise
            delay = _POOL_RETRY_BASE_DELAY * (2**attempt)
            log.warning(
                "Pool exhausted — retry %d/%d in %.0f ms",
                attempt + 1,
                _POOL_RETRY_ATTEMPTS,
                delay * 1000,
            )
            time.sleep(delay)

    try:
        yield conn
    finally:
        _pool.putconn(conn)


def fetch_all(
    query: str,
    params: tuple | dict | None = None,
) -> list[dict[str, Any]]:
    """Execute a SELECT and return all rows as dicts."""
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


def fetch_one(
    query: str,
    params: tuple | dict | None = None,
) -> dict[str, Any] | None:
    """Execute a SELECT and return the first row (or None)."""
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None


def fetch_scalar(
    query: str,
    params: tuple | dict | None = None,
) -> Any:
    """Execute a SELECT and return a single scalar value."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        return row[0] if row else None
