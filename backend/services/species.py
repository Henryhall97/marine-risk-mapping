"""Species query service — reads from fct_species_risk and crosswalk."""

from __future__ import annotations

from typing import Any

from backend.services.database import fetch_all, fetch_one, fetch_scalar

_BBOX_WHERE = (
    "cell_lat BETWEEN %(lat_min)s AND %(lat_max)s "
    "AND cell_lon BETWEEN %(lon_min)s AND %(lon_max)s"
)


def list_species() -> list[dict[str, Any]]:
    """List all species from the crosswalk seed.

    Returns species_group, common_name, scientific_name,
    is_baleen, and conservation_priority.
    """
    query = (
        "SELECT DISTINCT "
        "  species_group, common_name, scientific_name, "
        "  is_baleen, conservation_priority "
        "FROM species_crosswalk "
        "WHERE species_group IS NOT NULL "
        "ORDER BY species_group"
    )
    return fetch_all(query)


def list_crosswalk() -> list[dict[str, Any]]:
    """Return the full species crosswalk (all rows, all columns).

    Scientists can use this to understand how names map across
    OBIS, Nisi ISDM, and NMFS ship-strike databases.
    """
    query = (
        "SELECT scientific_name, common_name, species_group, "
        "  nisi_species, strike_species, taxonomic_rank, "
        "  family, is_baleen, conservation_priority, "
        "  aphia_id, worms_lsid "
        "FROM species_crosswalk "
        "ORDER BY family, scientific_name"
    )
    return fetch_all(query)


def resolve_species(
    species_key: str,
) -> dict[str, Any] | None:
    """Look up a species by scientific_name OR species_group.

    Returns ``{scientific_name, aphia_id, worms_lsid, taxonomic_rank}``
    or None.  Prefers exact ``scientific_name`` match at species rank;
    falls back to any rank match, then species_group lookup.
    """
    # Try exact scientific_name at species rank first
    row = fetch_one(
        "SELECT scientific_name, aphia_id, worms_lsid, taxonomic_rank "
        "FROM species_crosswalk "
        "WHERE lower(scientific_name) = lower(%s) "
        "  AND taxonomic_rank = 'species' "
        "LIMIT 1",
        (species_key,),
    )
    if row:
        return dict(row)
    # Try exact scientific_name at any rank (genus, family, etc.)
    row = fetch_one(
        "SELECT scientific_name, aphia_id, worms_lsid, taxonomic_rank "
        "FROM species_crosswalk "
        "WHERE lower(scientific_name) = lower(%s) "
        "ORDER BY CASE taxonomic_rank "
        "  WHEN 'species' THEN 1 WHEN 'genus' THEN 2 "
        "  WHEN 'family' THEN 3 WHEN 'suborder' THEN 4 "
        "  WHEN 'order' THEN 5 ELSE 6 END "
        "LIMIT 1",
        (species_key,),
    )
    if row:
        return dict(row)
    # Fall back to species_group — prefer species rank
    row = fetch_one(
        "SELECT scientific_name, aphia_id, worms_lsid, taxonomic_rank "
        "FROM species_crosswalk "
        "WHERE lower(species_group) = lower(%s) "
        "ORDER BY CASE taxonomic_rank "
        "  WHEN 'species' THEN 1 WHEN 'genus' THEN 2 "
        "  WHEN 'family' THEN 3 WHEN 'suborder' THEN 4 "
        "  WHEN 'order' THEN 5 ELSE 6 END "
        "LIMIT 1",
        (species_key,),
    )
    return dict(row) if row else None


def get_species_risk(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    species_group: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query per-species risk cells within a bounding box."""
    where_parts = [_BBOX_WHERE]
    params: dict[str, Any] = {
        "lat_min": lat_min,
        "lat_max": lat_max,
        "lon_min": lon_min,
        "lon_max": lon_max,
    }

    if species_group:
        where_parts.append("species_group = %(species_group)s")
        params["species_group"] = species_group

    where = " AND ".join(where_parts)
    params["limit"] = limit
    params["offset"] = offset

    query = (
        "SELECT "
        "  h3_cell, cell_lat, cell_lon, species, "
        "  common_name, species_group, is_baleen, "
        "  sighting_count, earliest_year, latest_year, "
        "  avg_monthly_vessels, avg_speed_knots, "
        "  depth_m, depth_zone, in_speed_zone, mpa_count, "
        "  species_risk_score "
        "FROM fct_species_risk "
        f"WHERE {where} "
        "ORDER BY species_risk_score DESC "
        "LIMIT %(limit)s OFFSET %(offset)s"
    )
    return fetch_all(query, params)


def count_species_risk(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    species_group: str | None = None,
) -> int:
    """Count species risk rows matching filters."""
    where_parts = [_BBOX_WHERE]
    params: dict[str, Any] = {
        "lat_min": lat_min,
        "lat_max": lat_max,
        "lon_min": lon_min,
        "lon_max": lon_max,
    }

    if species_group:
        where_parts.append("species_group = %(species_group)s")
        params["species_group"] = species_group

    where = " AND ".join(where_parts)
    query = f"SELECT count(*) FROM fct_species_risk WHERE {where}"
    return fetch_scalar(query, params) or 0
