"""Risk query service — reads from fct_collision_risk and seasonal marts."""

from __future__ import annotations

import math
from typing import Any

from backend.services.database import fetch_all, fetch_one, fetch_scalar

# ── Helpers ─────────────────────────────────────────────────

_BBOX_WHERE = (
    "cell_lat BETWEEN %(lat_min)s AND %(lat_max)s "
    "AND cell_lon BETWEEN %(lon_min)s AND %(lon_max)s"
)

_SUMMARY_COLS = "h3_cell, cell_lat, cell_lon, risk_score, risk_category"


def _bbox_params(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "lat_min": lat_min,
        "lat_max": lat_max,
        "lon_min": lon_min,
        "lon_max": lon_max,
        **extra,
    }


# ── Static risk zones ──────────────────────────────────────


def get_risk_zones(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    risk_category: str | None = None,
    min_risk_score: float | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query risk zone summaries within a bounding box."""
    where_parts = [_BBOX_WHERE]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)

    if risk_category:
        where_parts.append("risk_category = %(risk_category)s")
        params["risk_category"] = risk_category

    if min_risk_score is not None:
        where_parts.append("risk_score >= %(min_risk)s")
        params["min_risk"] = min_risk_score

    where = " AND ".join(where_parts)
    params["limit"] = limit
    params["offset"] = offset

    query = (
        f"SELECT {_SUMMARY_COLS} "
        f"FROM fct_collision_risk "
        f"WHERE {where} "
        f"ORDER BY risk_score DESC "
        f"LIMIT %(limit)s OFFSET %(offset)s"
    )
    return fetch_all(query, params)


def count_risk_zones(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    risk_category: str | None = None,
    min_risk_score: float | None = None,
) -> int:
    """Count risk zone rows matching filters."""
    where_parts = [_BBOX_WHERE]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)

    if risk_category:
        where_parts.append("risk_category = %(risk_category)s")
        params["risk_category"] = risk_category

    if min_risk_score is not None:
        where_parts.append("risk_score >= %(min_risk)s")
        params["min_risk"] = min_risk_score

    where = " AND ".join(where_parts)
    query = f"SELECT count(*) FROM fct_collision_risk WHERE {where}"
    return fetch_scalar(query, params) or 0


def get_risk_zone_detail(h3_cell: int) -> dict[str, Any] | None:
    """Full detail for a single H3 cell from fct_collision_risk."""
    query = "SELECT * FROM fct_collision_risk WHERE h3_cell = %s"
    return fetch_one(query, (h3_cell,))


# ── Nearest-cell fallback ──────────────────────────────────

_NEAREST_RADII_DEG = [2.0, 8.0, 20.0]


def _haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Great-circle distance between two points in km."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_nearest_risk_cell(
    lat: float,
    lon: float,
) -> dict[str, Any] | None:
    """Find nearest *fct_collision_risk* cell to *lat*/*lon*.

    Uses progressive bbox expansion for efficiency,
    returning the row dict augmented with ``distance_km``.
    """
    order_expr = (
        "power(cell_lat - %(lat)s, 2)"
        " + power("
        "(cell_lon - %(lon)s)"
        " * cos(radians(%(lat)s)), 2)"
    )

    for radius in _NEAREST_RADII_DEG:
        query = (
            "SELECT * FROM fct_collision_risk "
            "WHERE cell_lat "
            "BETWEEN %(lat_min)s AND %(lat_max)s "
            "AND cell_lon "
            "BETWEEN %(lon_min)s AND %(lon_max)s "
            f"ORDER BY {order_expr} LIMIT 1"
        )
        params: dict[str, Any] = {
            "lat": lat,
            "lon": lon,
            "lat_min": lat - radius,
            "lat_max": lat + radius,
            "lon_min": lon - radius,
            "lon_max": lon + radius,
        }
        row = fetch_one(query, params)
        if row:
            dist = _haversine_km(
                lat,
                lon,
                row["cell_lat"],
                row["cell_lon"],
            )
            return {
                **row,
                "distance_km": round(dist, 1),
            }

    # Global fallback — no bbox constraint
    query = f"SELECT * FROM fct_collision_risk ORDER BY {order_expr} LIMIT 1"
    row = fetch_one(query, {"lat": lat, "lon": lon})
    if row:
        dist = _haversine_km(
            lat,
            lon,
            row["cell_lat"],
            row["cell_lon"],
        )
        return {
            **row,
            "distance_km": round(dist, 1),
        }
    return None


def get_risk_stats(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> dict[str, Any] | None:
    """Aggregate risk statistics for a bounding box."""
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    query = (
        "SELECT "
        "  count(*) AS total_cells, "
        "  avg(risk_score)::float AS avg_risk_score, "
        "  max(risk_score)::float AS max_risk_score, "
        "  min(risk_score)::float AS min_risk_score "
        "FROM fct_collision_risk "
        f"WHERE {_BBOX_WHERE}"
    )
    row = fetch_one(query, params)
    if not row or row["total_cells"] == 0:
        return None

    # Category counts
    cat_query = (
        "SELECT risk_category, count(*) AS cnt "
        "FROM fct_collision_risk "
        f"WHERE {_BBOX_WHERE} "
        "GROUP BY risk_category"
    )
    cat_rows = fetch_all(cat_query, params)
    row["category_counts"] = {r["risk_category"]: r["cnt"] for r in cat_rows}
    return row


# ── Seasonal risk zones ────────────────────────────────────


def get_seasonal_risk_zones(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
    risk_category: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query seasonal risk zones within a bounding box."""
    cols = (
        "h3_cell, season, cell_lat, cell_lon, "
        "risk_score, risk_category, "
        "traffic_score, cetacean_score, proximity_score, "
        "strike_score, habitat_score, protection_gap, "
        "reference_risk_score, "
        "has_traffic, has_whale_sightings, in_mpa, "
        "has_strike_history, in_speed_zone, "
        "in_current_sma, in_proposed_zone, has_nisi_reference"
    )
    where_parts = [_BBOX_WHERE]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)

    if season:
        where_parts.append("season = %(season)s")
        params["season"] = season

    if risk_category:
        where_parts.append("risk_category = %(risk_category)s")
        params["risk_category"] = risk_category

    where = " AND ".join(where_parts)
    params["limit"] = limit
    params["offset"] = offset

    query = (
        f"SELECT {cols} "
        f"FROM fct_collision_risk_seasonal "
        f"WHERE {where} "
        f"ORDER BY risk_score DESC "
        f"LIMIT %(limit)s OFFSET %(offset)s"
    )
    return fetch_all(query, params)


def count_seasonal_risk_zones(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
    risk_category: str | None = None,
) -> int:
    """Count seasonal risk rows matching filters."""
    where_parts = [_BBOX_WHERE]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)

    if season:
        where_parts.append("season = %(season)s")
        params["season"] = season

    if risk_category:
        where_parts.append("risk_category = %(risk_category)s")
        params["risk_category"] = risk_category

    where = " AND ".join(where_parts)
    query = f"SELECT count(*) FROM fct_collision_risk_seasonal WHERE {where}"
    return fetch_scalar(query, params) or 0
