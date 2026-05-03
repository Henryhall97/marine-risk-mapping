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


# ── Biologically Important Areas ────────────────────────────


def _make_bbox_filter(
    params: dict[str, Any],
) -> str:
    """Return an ST_Intersects WHERE fragment using the bbox params."""
    return (
        "ST_Intersects("
        "  geom, "
        "  ST_MakeEnvelope("
        "    %(lon_min)s, %(lat_min)s, "
        "    %(lon_max)s, %(lat_max)s, 4326"
        "  )"
        ")"
    )


def get_bia_features(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    bia_type: str | None = None,
    species: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return BIA polygons intersecting a bounding box."""
    params: dict[str, Any] = {
        "lat_min": lat_min,
        "lat_max": lat_max,
        "lon_min": lon_min,
        "lon_max": lon_max,
    }
    where_parts = [_make_bbox_filter(params)]

    if bia_type:
        where_parts.append("bia_type = %(bia_type)s")
        params["bia_type"] = bia_type
    if species:
        where_parts.append(
            "(lower(sci_name) LIKE %(sp)s OR lower(cmn_name) LIKE %(sp)s)"
        )
        params["sp"] = f"%{species.lower()}%"

    where = " AND ".join(where_parts)
    params["limit"] = limit
    params["offset"] = offset

    query = (
        "SELECT "
        "  id, bia_id, region, sci_name, cmn_name, "
        "  bia_name, bia_type, bia_months, "
        "  ST_AsGeoJSON(ST_MakeValid(geom))::json AS geometry "
        "FROM cetacean_bia "
        f"WHERE {where} "
        "ORDER BY bia_type, cmn_name "
        "LIMIT %(limit)s OFFSET %(offset)s"
    )
    rows = fetch_all(query, params)
    for row in rows:
        if isinstance(row.get("geometry"), str):
            row["geometry"] = json.loads(row["geometry"])
    return rows


def count_bia_features(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    bia_type: str | None = None,
    species: str | None = None,
) -> int:
    """Count BIAs intersecting a bounding box."""
    params: dict[str, Any] = {
        "lat_min": lat_min,
        "lat_max": lat_max,
        "lon_min": lon_min,
        "lon_max": lon_max,
    }
    where_parts = [_make_bbox_filter(params)]
    if bia_type:
        where_parts.append("bia_type = %(bia_type)s")
        params["bia_type"] = bia_type
    if species:
        where_parts.append(
            "(lower(sci_name) LIKE %(sp)s OR lower(cmn_name) LIKE %(sp)s)"
        )
        params["sp"] = f"%{species.lower()}%"
    where = " AND ".join(where_parts)
    return (
        fetch_scalar(
            f"SELECT count(*) FROM cetacean_bia WHERE {where}",
            params,
        )
        or 0
    )


# ── Critical Habitat ────────────────────────────────────────


def get_critical_habitat(
    species: str | None = None,
) -> list[dict[str, Any]]:
    """Return all whale Critical Habitat polygons.

    Small dataset (31 rows) — no bbox needed; return all
    and let the frontend render only visible ones.
    """
    where_parts: list[str] = []
    params: dict[str, Any] = {}

    if species:
        where_parts.append("(species_label LIKE %(sp)s OR lower(sci_name) LIKE %(sp)s)")
        params["sp"] = f"%{species.lower()}%"

    where = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""

    query = (
        "SELECT "
        "  id, species_label, sci_name, cmn_name, "
        "  list_status, ch_status, unit, area_sq_km, "
        "  is_proposed, "
        "  ST_AsGeoJSON(ST_MakeValid(geom))::json AS geometry "
        "FROM whale_critical_habitat"
        f"{where} "
        "ORDER BY species_label"
    )
    rows = fetch_all(query, params)
    for row in rows:
        if isinstance(row.get("geometry"), str):
            row["geometry"] = json.loads(row["geometry"])
    return rows


# ── Shipping Lanes ──────────────────────────────────────────


def get_shipping_lanes(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    zone_type: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return shipping lane polygons intersecting a bounding box."""
    params: dict[str, Any] = {
        "lat_min": lat_min,
        "lat_max": lat_max,
        "lon_min": lon_min,
        "lon_max": lon_max,
    }
    where_parts = [_make_bbox_filter(params)]

    if zone_type:
        where_parts.append("zone_type = %(zone_type)s")
        params["zone_type"] = zone_type

    where = " AND ".join(where_parts)
    params["limit"] = limit
    params["offset"] = offset

    query = (
        "SELECT "
        "  id, zone_type, name, description, "
        "  ST_AsGeoJSON(geom)::json AS geometry "
        "FROM shipping_lanes "
        f"WHERE {where} "
        "ORDER BY zone_type, name "
        "LIMIT %(limit)s OFFSET %(offset)s"
    )
    rows = fetch_all(query, params)
    for row in rows:
        if isinstance(row.get("geometry"), str):
            row["geometry"] = json.loads(row["geometry"])
    return rows


def count_shipping_lanes(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    zone_type: str | None = None,
) -> int:
    """Count shipping lanes intersecting a bounding box."""
    params: dict[str, Any] = {
        "lat_min": lat_min,
        "lat_max": lat_max,
        "lon_min": lon_min,
        "lon_max": lon_max,
    }
    where_parts = [_make_bbox_filter(params)]
    if zone_type:
        where_parts.append("zone_type = %(zone_type)s")
        params["zone_type"] = zone_type
    where = " AND ".join(where_parts)
    return (
        fetch_scalar(
            f"SELECT count(*) FROM shipping_lanes WHERE {where}",
            params,
        )
        or 0
    )


# ── Slow Zones ──────────────────────────────────────────────


def get_slow_zones() -> list[dict[str, Any]]:
    """Return all Right Whale Slow Zones with expiry flag.

    Small dataset (≤10 rows) — no bbox or pagination needed.
    """
    query = (
        "SELECT "
        "  id, zone_name, zone_type, "
        "  effective_start::text AS effective_start, "
        "  effective_end::text AS effective_end, "
        "  speed_limit_kn, voluntary, duration_days, "
        "  (effective_end < CURRENT_DATE) AS is_expired, "
        "  ST_AsGeoJSON(geom)::json AS geometry "
        "FROM right_whale_slow_zones "
        "ORDER BY effective_end DESC"
    )
    rows = fetch_all(query)
    for row in rows:
        if isinstance(row.get("geometry"), str):
            row["geometry"] = json.loads(row["geometry"])
    return rows
