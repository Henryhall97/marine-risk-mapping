"""Traffic query service — reads from fct_monthly_traffic."""

from __future__ import annotations

from typing import Any

from backend.services.database import fetch_all, fetch_scalar

_BBOX_WHERE = (
    "cell_lat BETWEEN %(lat_min)s AND %(lat_max)s "
    "AND cell_lon BETWEEN %(lon_min)s AND %(lon_max)s"
)


def get_monthly_traffic(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    month_start: str | None = None,
    month_end: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query monthly traffic cells within a bounding box.

    Parameters
    ----------
    month_start / month_end : str | None
        ISO date strings (YYYY-MM-DD) for filtering the month
        column.  Both are optional and inclusive.
    """
    where_parts = [_BBOX_WHERE]
    params: dict[str, Any] = {
        "lat_min": lat_min,
        "lat_max": lat_max,
        "lon_min": lon_min,
        "lon_max": lon_max,
    }

    if month_start:
        where_parts.append("month >= %(month_start)s::date")
        params["month_start"] = month_start

    if month_end:
        where_parts.append("month <= %(month_end)s::date")
        params["month_end"] = month_end

    where = " AND ".join(where_parts)
    params["limit"] = limit
    params["offset"] = offset

    query = (
        "SELECT "
        "  h3_cell, month::text AS month, cell_lat, cell_lon, "
        "  unique_vessels, ping_count, "
        "  vw_avg_speed_knots, max_speed_knots, "
        "  high_speed_vessel_count, large_vessel_count, "
        "  day_unique_vessels, night_unique_vessels, "
        "  cargo_vessels, tanker_vessels, "
        "  fishing_vessels, passenger_vessels, "
        "  depth_zone, is_continental_shelf, in_mpa "
        "FROM fct_monthly_traffic "
        f"WHERE {where} "
        "ORDER BY month DESC, unique_vessels DESC "
        "LIMIT %(limit)s OFFSET %(offset)s"
    )
    return fetch_all(query, params)


def count_monthly_traffic(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    month_start: str | None = None,
    month_end: str | None = None,
) -> int:
    """Count monthly traffic rows matching filters."""
    where_parts = [_BBOX_WHERE]
    params: dict[str, Any] = {
        "lat_min": lat_min,
        "lat_max": lat_max,
        "lon_min": lon_min,
        "lon_max": lon_max,
    }

    if month_start:
        where_parts.append("month >= %(month_start)s::date")
        params["month_start"] = month_start

    if month_end:
        where_parts.append("month <= %(month_end)s::date")
        params["month_end"] = month_end

    where = " AND ".join(where_parts)
    query = f"SELECT count(*) FROM fct_monthly_traffic WHERE {where}"
    return fetch_scalar(query, params) or 0
