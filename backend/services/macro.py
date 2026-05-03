"""Service layer for macro overview queries.

Includes a lightweight in-memory TTL cache — the macro overview
table is pre-aggregated and changes only when the aggregation
pipeline reruns (hours/days), so caching avoids repeated DB
round-trips for the same (season, scenario, decade) query.
"""

from __future__ import annotations

import logging
import time

from backend.services.database import fetch_all, fetch_scalar

logger = logging.getLogger(__name__)

VALID_SEASONS = {"annual", "winter", "spring", "summer", "fall"}

# ── In-memory TTL cache ─────────────────────────────────────
# Key: (season, scenario, decade) → (timestamp, rows)
_CACHE_TTL_SECONDS = 300  # 5 minutes
_cache: dict[tuple, tuple[float, list[dict]]] = {}
_count_cache: dict[tuple, tuple[float, int]] = {}


def _cache_key(
    season: str,
    scenario: str | None,
    decade: str | None,
) -> tuple:
    return (season, scenario, decade)


def invalidate_macro_cache() -> None:
    """Clear all cached macro data (call after pipeline refresh)."""
    _cache.clear()
    _count_cache.clear()
    logger.info("Macro overview cache invalidated")


def get_macro_overview(
    season: str = "annual",
    scenario: str | None = None,
    decade: str | None = None,
) -> list[dict]:
    """Return all coarse H3 res-4 cells for a given season.

    For current data pass scenario=None, decade=None (the defaults).
    For projected data pass e.g. scenario="ssp245", decade="2030s".

    Results are cached in memory for up to 5 minutes.
    """
    if season not in VALID_SEASONS:
        season = "annual"

    key = _cache_key(season, scenario, decade)
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]

    sql = """
        SELECT h3_cell, cell_lat, cell_lon, season,
               scenario, decade,
               risk_score, ml_risk_score, traffic_score,
               avg_monthly_vessels, avg_speed_lethality,
               avg_high_speed_fraction, avg_draft_risk_fraction,
               night_traffic_ratio, avg_commercial_vessels,
               cetacean_score,
               strike_score, habitat_score, proximity_score,
               protection_gap, reference_risk,
               total_sightings, baleen_sightings, total_strikes,
               any_whale_prob, isdm_blue_whale, isdm_fin_whale,
               isdm_humpback_whale, isdm_sperm_whale,
               sdm_any_whale, sdm_blue_whale, sdm_fin_whale,
               sdm_humpback_whale, sdm_sperm_whale,
               sdm_right_whale, sdm_minke_whale,
               sst, sst_sd, mld, sla, pp_upper_200m,
               depth_m_mean, shelf_fraction,
               child_cell_count
        FROM macro_risk_overview
        WHERE season = %(season)s
    """
    params: dict = {"season": season}

    if scenario is not None and decade is not None:
        sql += "  AND scenario = %(scenario)s  AND decade = %(decade)s"
        params["scenario"] = scenario
        params["decade"] = decade
    else:
        sql += "  AND scenario IS NULL"

    sql += "\n        ORDER BY h3_cell"
    rows = fetch_all(sql, params)
    _cache[key] = (now, rows)
    return rows


def count_macro_overview(
    season: str = "annual",
    scenario: str | None = None,
    decade: str | None = None,
) -> int:
    """Count cells for a given season (and optional projection)."""
    if season not in VALID_SEASONS:
        season = "annual"

    key = _cache_key(season, scenario, decade)
    now = time.monotonic()
    cached = _count_cache.get(key)
    if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]

    sql = """
        SELECT count(*)
        FROM macro_risk_overview
        WHERE season = %(season)s
    """
    params: dict = {"season": season}

    if scenario is not None and decade is not None:
        sql += "  AND scenario = %(scenario)s  AND decade = %(decade)s"
        params["scenario"] = scenario
        params["decade"] = decade
    else:
        sql += "  AND scenario IS NULL"

    result = fetch_scalar(sql, params) or 0
    _count_cache[key] = (now, result)
    return result
