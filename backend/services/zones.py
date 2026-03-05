"""Zone geometry query services.

Returns actual polygon geometries (as GeoJSON dicts) for
speed zones and MPAs — suitable for map overlay rendering.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from backend.services.database import fetch_all, fetch_scalar


def _is_zone_active(
    row: dict[str, Any],
    check_date: date,
) -> bool:
    """Determine if a zone is active on *check_date*.

    Handles year-wrapping ranges (e.g. Nov 1 → Apr 30).
    """
    md = check_date.month * 100 + check_date.day
    start = row["start_month"] * 100 + row["start_day"]
    end = row["end_month"] * 100 + row["end_day"]
    if start <= end:
        # Same-year range (e.g. Mar 1 – Jul 31)
        return start <= md <= end
    # Year-wrapping range (e.g. Nov 1 – Apr 30)
    return md >= start or md <= end


# ── Current SMAs ────────────────────────────────────────────


def get_current_speed_zones(
    check_date: date | None = None,
) -> list[dict[str, Any]]:
    """Return all active Seasonal Management Areas with geometry.

    When *check_date* is provided each row gets an ``is_active``
    boolean indicating whether the zone's seasonal window covers
    that date.  Defaults to today.
    """
    use_date = check_date or date.today()
    query = (
        "SELECT "
        "  id, zone_name, zone_abbr, "
        "  start_month, start_day, end_month, end_day, "
        "  area_sq_deg, perimeter_deg, "
        "  to_char(make_date(2000, start_month, start_day), "
        "    'Mon DD') || ' – ' || "
        "  to_char(make_date(2000, end_month, end_day), "
        "    'Mon DD') AS season_label, "
        "  ST_AsGeoJSON(geom)::json AS geometry "
        "FROM seasonal_management_areas "
        "ORDER BY zone_name"
    )
    rows = fetch_all(query)
    for row in rows:
        if isinstance(row.get("geometry"), str):
            row["geometry"] = json.loads(row["geometry"])
        row["is_active"] = _is_zone_active(row, use_date)
    return rows


# ── Proposed speed zones ────────────────────────────────────


def get_proposed_speed_zones(
    check_date: date | None = None,
) -> list[dict[str, Any]]:
    """Return all proposed NARW speed restriction zones.

    When *check_date* is provided each row gets an ``is_active``
    boolean.  Defaults to today.
    """
    use_date = check_date or date.today()
    query = (
        "SELECT "
        "  id, zone_name, "
        "  start_month, start_day, end_month, end_day, "
        "  area_sq_deg, perimeter_deg, "
        "  to_char(make_date(2000, start_month, start_day), "
        "    'Mon DD') || ' – ' || "
        "  to_char(make_date(2000, end_month, end_day), "
        "    'Mon DD') AS season_label, "
        "  ST_AsGeoJSON(geom)::json AS geometry "
        "FROM right_whale_speed_zones "
        "ORDER BY zone_name"
    )
    rows = fetch_all(query)
    for row in rows:
        if isinstance(row.get("geometry"), str):
            row["geometry"] = json.loads(row["geometry"])
        row["is_active"] = _is_zone_active(row, use_date)
    return rows


def get_mpa_features(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    protection_level: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return MPA polygons intersecting a bounding box."""
    where_parts = [
        "ST_Intersects("
        "  geom, "
        "  ST_MakeEnvelope("
        "    %(lon_min)s, %(lat_min)s, "
        "    %(lon_max)s, %(lat_max)s, 4326"
        "  )"
        ")",
        "mar_percent > 0",
    ]
    params: dict[str, Any] = {
        "lat_min": lat_min,
        "lat_max": lat_max,
        "lon_min": lon_min,
        "lon_max": lon_max,
    }

    if protection_level:
        where_parts.append("prot_lvl = %(prot_lvl)s")
        params["prot_lvl"] = protection_level

    where = " AND ".join(where_parts)
    params["limit"] = limit
    params["offset"] = offset

    query = (
        "SELECT "
        "  id, site_id, site_name, "
        "  gov_level, state, "
        "  prot_lvl AS protection_level, "
        "  mgmt_agen AS managing_agency, "
        "  iucn_cat AS iucn_category, "
        "  nullif(estab_yr, 0) AS established_year, "
        "  area_km AS area_total_km2, "
        "  area_mar AS area_marine_km2, "
        "  mar_percent AS marine_percent, "
        "  ST_AsGeoJSON(ST_MakeValid(geom))::json "
        "    AS geometry "
        "FROM marine_protected_areas "
        f"WHERE {where} "
        "ORDER BY area_mar DESC NULLS LAST "
        f"LIMIT %(limit)s OFFSET %(offset)s"
    )
    rows = fetch_all(query, params)
    for row in rows:
        if isinstance(row.get("geometry"), str):
            row["geometry"] = json.loads(row["geometry"])
    return rows


def count_mpa_features(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    protection_level: str | None = None,
) -> int:
    """Count MPAs intersecting a bounding box."""
    where_parts = [
        "ST_Intersects("
        "  geom, "
        "  ST_MakeEnvelope("
        "    %(lon_min)s, %(lat_min)s, "
        "    %(lon_max)s, %(lat_max)s, 4326"
        "  )"
        ")",
        "mar_percent > 0",
    ]
    params: dict[str, Any] = {
        "lat_min": lat_min,
        "lat_max": lat_max,
        "lon_min": lon_min,
        "lon_max": lon_max,
    }
    if protection_level:
        where_parts.append("prot_lvl = %(prot_lvl)s")
        params["prot_lvl"] = protection_level

    where = " AND ".join(where_parts)
    query = f"SELECT count(*) FROM marine_protected_areas WHERE {where}"
    return fetch_scalar(query, params) or 0
