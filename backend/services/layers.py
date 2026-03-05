"""Layer query services — spatial overlays from intermediate tables.

Each function returns dicts suitable for Pydantic model construction.
Uses the same bbox-filter + pagination pattern as existing services.
"""

from __future__ import annotations

from typing import Any

from backend.services.database import fetch_all, fetch_one, fetch_scalar

# ── Shared helpers ──────────────────────────────────────────

_BBOX_WHERE = (
    "g.cell_lat BETWEEN %(lat_min)s AND %(lat_max)s "
    "AND g.cell_lon BETWEEN %(lon_min)s AND %(lon_max)s"
)

# For tables that already have cell_lat/cell_lon directly
_BBOX_WHERE_DIRECT = (
    "cell_lat BETWEEN %(lat_min)s AND %(lat_max)s "
    "AND cell_lon BETWEEN %(lon_min)s AND %(lon_max)s"
)


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


# ── Bathymetry ──────────────────────────────────────────────


def get_bathymetry(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    depth_zone: str | None = None,
    exclude_land: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query bathymetry cells within a bounding box."""
    where_parts = [_BBOX_WHERE]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)

    if exclude_land:
        where_parts.append("b.is_land = false")

    if depth_zone:
        where_parts.append("b.depth_zone = %(depth_zone)s")
        params["depth_zone"] = depth_zone

    where = " AND ".join(where_parts)
    params["limit"] = limit
    params["offset"] = offset

    query = (
        "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
        "  b.depth_m, b.min_depth_m, b.max_depth_m, "
        "  b.depth_range_m, b.depth_zone, "
        "  b.is_continental_shelf, b.is_shelf_edge, b.is_land "
        "FROM int_hex_grid g "
        "JOIN int_bathymetry b ON g.h3_cell = b.h3_cell "
        f"WHERE {where} "
        "ORDER BY b.depth_m "
        f"LIMIT %(limit)s OFFSET %(offset)s"
    )
    return fetch_all(query, params)


def count_bathymetry(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    depth_zone: str | None = None,
    exclude_land: bool = True,
) -> int:
    """Count bathymetry rows in bbox."""
    where_parts = [_BBOX_WHERE]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    if exclude_land:
        where_parts.append("b.is_land = false")
    if depth_zone:
        where_parts.append("b.depth_zone = %(depth_zone)s")
        params["depth_zone"] = depth_zone
    where = " AND ".join(where_parts)
    query = (
        "SELECT count(*) FROM int_hex_grid g "
        "JOIN int_bathymetry b ON g.h3_cell = b.h3_cell "
        f"WHERE {where}"
    )
    return fetch_scalar(query, params) or 0


# ── Ocean covariates ────────────────────────────────────────


def get_ocean_covariates(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query ocean covariates — annual mean, single season, or all."""
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    params["limit"] = limit
    params["offset"] = offset

    if season == "all":
        # All 4 seasons — seasonal table, no season filter
        where = _BBOX_WHERE
        query = (
            "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
            "  o.season, o.sst, o.sst_sd, o.mld, "
            "  o.sla, o.pp_upper_200m "
            "FROM int_hex_grid g "
            "JOIN int_ocean_covariates_seasonal o "
            "  ON g.h3_cell = o.h3_cell "
            f"WHERE {where} "
            "ORDER BY g.h3_cell, o.season "
            f"LIMIT %(limit)s OFFSET %(offset)s"
        )
    elif season:
        # Single season
        where_parts = [_BBOX_WHERE]
        where_parts.append("o.season = %(season)s")
        params["season"] = season
        where = " AND ".join(where_parts)
        query = (
            "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
            "  o.season, o.sst, o.sst_sd, o.mld, "
            "  o.sla, o.pp_upper_200m "
            "FROM int_hex_grid g "
            "JOIN int_ocean_covariates_seasonal o "
            "  ON g.h3_cell = o.h3_cell "
            f"WHERE {where} "
            "ORDER BY o.sst DESC NULLS LAST "
            f"LIMIT %(limit)s OFFSET %(offset)s"
        )
    else:
        # Annual mean
        where = _BBOX_WHERE
        query = (
            "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
            "  NULL AS season, o.sst, o.sst_sd, o.mld, "
            "  o.sla, o.pp_upper_200m "
            "FROM int_hex_grid g "
            "JOIN int_ocean_covariates o ON g.h3_cell = o.h3_cell "
            f"WHERE {where} "
            "ORDER BY o.sst DESC NULLS LAST "
            f"LIMIT %(limit)s OFFSET %(offset)s"
        )
    return fetch_all(query, params)


def count_ocean_covariates(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
) -> int:
    """Count ocean covariate rows in bbox."""
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    if season == "all":
        # All 4 seasons — no season filter
        query = (
            "SELECT count(*) FROM int_hex_grid g "
            "JOIN int_ocean_covariates_seasonal o "
            "  ON g.h3_cell = o.h3_cell "
            f"WHERE {_BBOX_WHERE}"
        )
    elif season:
        where_parts = [_BBOX_WHERE]
        where_parts.append("o.season = %(season)s")
        params["season"] = season
        where = " AND ".join(where_parts)
        query = (
            "SELECT count(*) FROM int_hex_grid g "
            "JOIN int_ocean_covariates_seasonal o "
            "  ON g.h3_cell = o.h3_cell "
            f"WHERE {where}"
        )
    else:
        query = (
            "SELECT count(*) FROM int_hex_grid g "
            "JOIN int_ocean_covariates o ON g.h3_cell = o.h3_cell "
            f"WHERE {_BBOX_WHERE}"
        )
    return fetch_scalar(query, params) or 0


# ── Whale predictions (ISDM) ───────────────────────────────


def get_whale_predictions(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
    species: str | None = None,
    min_probability: float | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query ISDM whale predictions within a bounding box."""
    where_parts = [_BBOX_WHERE]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)

    if season:
        where_parts.append("w.season = %(season)s")
        params["season"] = season

    if species and min_probability is not None:
        col = f"w.isdm_{species}"
        where_parts.append(f"{col} >= %(min_prob)s")
        params["min_prob"] = min_probability
    elif min_probability is not None:
        where_parts.append("w.any_whale_prob >= %(min_prob)s")
        params["min_prob"] = min_probability

    where = " AND ".join(where_parts)
    params["limit"] = limit
    params["offset"] = offset

    query = (
        "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
        "  w.season, "
        "  w.isdm_blue_whale, w.isdm_fin_whale, "
        "  w.isdm_humpback_whale, w.isdm_sperm_whale, "
        "  w.max_whale_prob, w.mean_whale_prob, "
        "  w.any_whale_prob "
        "FROM int_hex_grid g "
        "JOIN int_ml_whale_predictions w ON g.h3_cell = w.h3_cell "
        f"WHERE {where} "
        "ORDER BY w.any_whale_prob DESC "
        f"LIMIT %(limit)s OFFSET %(offset)s"
    )
    return fetch_all(query, params)


def count_whale_predictions(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
    species: str | None = None,
    min_probability: float | None = None,
) -> int:
    """Count whale prediction rows in bbox."""
    where_parts = [_BBOX_WHERE]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)

    if season:
        where_parts.append("w.season = %(season)s")
        params["season"] = season

    if species and min_probability is not None:
        col = f"w.isdm_{species}"
        where_parts.append(f"{col} >= %(min_prob)s")
        params["min_prob"] = min_probability
    elif min_probability is not None:
        where_parts.append("w.any_whale_prob >= %(min_prob)s")
        params["min_prob"] = min_probability

    where = " AND ".join(where_parts)
    query = (
        "SELECT count(*) FROM int_hex_grid g "
        "JOIN int_ml_whale_predictions w ON g.h3_cell = w.h3_cell "
        f"WHERE {where}"
    )
    return fetch_scalar(query, params) or 0


# ── SDM whale predictions (OBIS-trained) ────────────────────


def get_sdm_predictions(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
    species: str | None = None,
    min_probability: float | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query SDM (OBIS-trained) whale predictions within a bbox."""
    where_parts = [_BBOX_WHERE]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)

    if season:
        where_parts.append("s.season = %(season)s")
        params["season"] = season

    if species and min_probability is not None:
        col = f"s.sdm_{species}"
        where_parts.append(f"{col} >= %(min_prob)s")
        params["min_prob"] = min_probability
    elif min_probability is not None:
        where_parts.append("s.sdm_any_whale >= %(min_prob)s")
        params["min_prob"] = min_probability

    where = " AND ".join(where_parts)
    params["limit"] = limit
    params["offset"] = offset

    query = (
        "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
        "  s.season, "
        "  s.sdm_any_whale, "
        "  s.sdm_blue_whale, s.sdm_fin_whale, "
        "  s.sdm_humpback_whale, s.sdm_sperm_whale, "
        "  s.max_whale_prob, s.mean_whale_prob, "
        "  s.any_whale_prob_joint "
        "FROM int_hex_grid g "
        "JOIN int_sdm_whale_predictions s "
        "  ON g.h3_cell = s.h3_cell "
        f"WHERE {where} "
        "ORDER BY s.sdm_any_whale DESC "
        f"LIMIT %(limit)s OFFSET %(offset)s"
    )
    return fetch_all(query, params)


def count_sdm_predictions(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
    species: str | None = None,
    min_probability: float | None = None,
) -> int:
    """Count SDM prediction rows in bbox."""
    where_parts = [_BBOX_WHERE]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)

    if season:
        where_parts.append("s.season = %(season)s")
        params["season"] = season

    if species and min_probability is not None:
        col = f"s.sdm_{species}"
        where_parts.append(f"{col} >= %(min_prob)s")
        params["min_prob"] = min_probability
    elif min_probability is not None:
        where_parts.append("s.sdm_any_whale >= %(min_prob)s")
        params["min_prob"] = min_probability

    where = " AND ".join(where_parts)
    query = (
        "SELECT count(*) FROM int_hex_grid g "
        "JOIN int_sdm_whale_predictions s "
        "  ON g.h3_cell = s.h3_cell "
        f"WHERE {where}"
    )
    return fetch_scalar(query, params) or 0


# ── MPA coverage ────────────────────────────────────────────


def get_mpa_coverage(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query MPA coverage cells within a bounding box."""
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    params["limit"] = limit
    params["offset"] = offset
    query = (
        "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
        "  m.mpa_count, m.mpa_names, "
        "  m.protection_level, m.has_no_take_zone "
        "FROM int_hex_grid g "
        "JOIN int_mpa_coverage m ON g.h3_cell = m.h3_cell "
        f"WHERE {_BBOX_WHERE} "
        "ORDER BY m.mpa_count DESC "
        f"LIMIT %(limit)s OFFSET %(offset)s"
    )
    return fetch_all(query, params)


def count_mpa_coverage(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> int:
    """Count MPA coverage rows in bbox."""
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    query = (
        "SELECT count(*) FROM int_hex_grid g "
        "JOIN int_mpa_coverage m ON g.h3_cell = m.h3_cell "
        f"WHERE {_BBOX_WHERE}"
    )
    return fetch_scalar(query, params) or 0


# ── Speed zones ─────────────────────────────────────────────


def get_speed_zones(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query speed zone coverage — static or seasonal."""
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    params["limit"] = limit
    params["offset"] = offset

    if season:
        where_parts = [_BBOX_WHERE]
        where_parts.append("s.season = %(season)s")
        params["season"] = season
        where = " AND ".join(where_parts)
        query = (
            "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
            "  s.season, s.zone_count, s.zone_names, "
            "  s.current_sma_count, s.proposed_zone_count, "
            "  s.max_season_days, s.season_labels "
            "FROM int_hex_grid g "
            "JOIN int_speed_zone_coverage_seasonal s "
            "  ON g.h3_cell = s.h3_cell "
            f"WHERE {where} "
            "ORDER BY s.zone_count DESC "
            f"LIMIT %(limit)s OFFSET %(offset)s"
        )
    else:
        query = (
            "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
            "  NULL AS season, s.zone_count, s.zone_names, "
            "  s.current_sma_count, s.proposed_zone_count, "
            "  s.max_season_days, s.season_labels "
            "FROM int_hex_grid g "
            "JOIN int_speed_zone_coverage s ON g.h3_cell = s.h3_cell "
            f"WHERE {_BBOX_WHERE} "
            "ORDER BY s.zone_count DESC "
            f"LIMIT %(limit)s OFFSET %(offset)s"
        )
    return fetch_all(query, params)


def count_speed_zones(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
) -> int:
    """Count speed zone rows in bbox."""
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    if season:
        where_parts = [_BBOX_WHERE]
        where_parts.append("s.season = %(season)s")
        params["season"] = season
        where = " AND ".join(where_parts)
        query = (
            "SELECT count(*) FROM int_hex_grid g "
            "JOIN int_speed_zone_coverage_seasonal s "
            "  ON g.h3_cell = s.h3_cell "
            f"WHERE {where}"
        )
    else:
        query = (
            "SELECT count(*) FROM int_hex_grid g "
            "JOIN int_speed_zone_coverage s "
            "  ON g.h3_cell = s.h3_cell "
            f"WHERE {_BBOX_WHERE}"
        )
    return fetch_scalar(query, params) or 0


# ── Proximity ───────────────────────────────────────────────


def get_proximity(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query proximity distances and decay scores in a bounding box."""
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    params["limit"] = limit
    params["offset"] = offset
    query = (
        "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
        "  p.dist_to_nearest_whale_km, "
        "  p.dist_to_nearest_ship_km, "
        "  p.dist_to_nearest_strike_km, "
        "  p.dist_to_nearest_protection_km, "
        "  p.whale_proximity_score, "
        "  p.ship_proximity_score, "
        "  p.strike_proximity_score, "
        "  p.protection_proximity_score "
        "FROM int_hex_grid g "
        "JOIN int_proximity p ON g.h3_cell = p.h3_cell "
        f"WHERE {_BBOX_WHERE} "
        "ORDER BY p.whale_proximity_score DESC "
        f"LIMIT %(limit)s OFFSET %(offset)s"
    )
    return fetch_all(query, params)


def count_proximity(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> int:
    """Count proximity rows in bbox."""
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    query = (
        "SELECT count(*) FROM int_hex_grid g "
        "JOIN int_proximity p ON g.h3_cell = p.h3_cell "
        f"WHERE {_BBOX_WHERE}"
    )
    return fetch_scalar(query, params) or 0


# ── Nisi reference risk ─────────────────────────────────────


def get_nisi_risk(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query Nisi reference risk within a bounding box."""
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    params["limit"] = limit
    params["offset"] = offset
    query = (
        "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
        "  n.nisi_all_risk, n.nisi_shipping_index, "
        "  n.nisi_whale_space_use, "
        "  n.nisi_blue_risk, n.nisi_fin_risk, "
        "  n.nisi_humpback_risk, n.nisi_sperm_risk, "
        "  n.nisi_has_management, n.nisi_has_mandatory_mgmt, "
        "  n.nisi_hotspot_overlap "
        "FROM int_hex_grid g "
        "JOIN int_nisi_reference_risk n ON g.h3_cell = n.h3_cell "
        f"WHERE {_BBOX_WHERE} "
        "ORDER BY n.nisi_all_risk DESC NULLS LAST "
        f"LIMIT %(limit)s OFFSET %(offset)s"
    )
    return fetch_all(query, params)


def count_nisi_risk(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> int:
    """Count Nisi risk rows in bbox."""
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    query = (
        "SELECT count(*) FROM int_hex_grid g "
        "JOIN int_nisi_reference_risk n ON g.h3_cell = n.h3_cell "
        f"WHERE {_BBOX_WHERE}"
    )
    return fetch_scalar(query, params) or 0


# ── Cetacean density ────────────────────────────────────────


def get_cetacean_density(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    min_sightings: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query cetacean sighting density (static) in a bounding box."""
    where_parts = [_BBOX_WHERE]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)

    if min_sightings is not None:
        where_parts.append("c.total_sightings >= %(min_sightings)s")
        params["min_sightings"] = min_sightings

    where = " AND ".join(where_parts)
    params["limit"] = limit
    params["offset"] = offset

    query = (
        "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
        "  NULL AS season, "
        "  c.total_sightings, c.unique_species, "
        "  c.baleen_whale_sightings AS baleen_sightings, "
        "  c.recent_sightings, "
        "  c.right_whale_sightings, c.humpback_sightings, "
        "  c.fin_whale_sightings, c.blue_whale_sightings, "
        "  c.sperm_whale_sightings, c.minke_whale_sightings "
        "FROM int_hex_grid g "
        "JOIN int_cetacean_density c ON g.h3_cell = c.h3_cell "
        f"WHERE {where} "
        "ORDER BY c.total_sightings DESC "
        f"LIMIT %(limit)s OFFSET %(offset)s"
    )
    return fetch_all(query, params)


def count_cetacean_density(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    min_sightings: int | None = None,
) -> int:
    """Count cetacean density rows in bbox."""
    where_parts = [_BBOX_WHERE]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    if min_sightings is not None:
        where_parts.append("c.total_sightings >= %(min_sightings)s")
        params["min_sightings"] = min_sightings
    where = " AND ".join(where_parts)
    query = (
        "SELECT count(*) FROM int_hex_grid g "
        "JOIN int_cetacean_density c ON g.h3_cell = c.h3_cell "
        f"WHERE {where}"
    )
    return fetch_scalar(query, params) or 0


# ── Ship strike density ─────────────────────────────────────


def get_strike_density(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query ship strike density (only ~67 cells)."""
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    params["limit"] = limit
    params["offset"] = offset
    query = (
        "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
        "  s.total_strikes, s.fatal_strikes, "
        "  s.serious_injury_strikes, s.baleen_strikes, "
        "  s.right_whale_strikes, "
        "  s.unique_species_groups, s.species_list "
        "FROM int_hex_grid g "
        "JOIN int_ship_strike_density s ON g.h3_cell = s.h3_cell "
        f"WHERE {_BBOX_WHERE} "
        "ORDER BY s.total_strikes DESC "
        f"LIMIT %(limit)s OFFSET %(offset)s"
    )
    return fetch_all(query, params)


def count_strike_density(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> int:
    """Count strike density rows in bbox."""
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    query = (
        "SELECT count(*) FROM int_hex_grid g "
        "JOIN int_ship_strike_density s ON g.h3_cell = s.h3_cell "
        f"WHERE {_BBOX_WHERE}"
    )
    return fetch_scalar(query, params) or 0


# ── ML risk ─────────────────────────────────────────────────


def get_ml_risk_zones(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
    risk_category: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query ML-enhanced risk zones within a bounding box."""
    where_parts = [_BBOX_WHERE_DIRECT]
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
        "SELECT h3_cell, season, cell_lat, cell_lon, "
        "  risk_score, risk_category "
        "FROM fct_collision_risk_ml "
        f"WHERE {where} "
        "ORDER BY risk_score DESC "
        f"LIMIT %(limit)s OFFSET %(offset)s"
    )
    return fetch_all(query, params)


def count_ml_risk_zones(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
    risk_category: str | None = None,
) -> int:
    """Count ML risk rows matching filters."""
    where_parts = [_BBOX_WHERE_DIRECT]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    if season:
        where_parts.append("season = %(season)s")
        params["season"] = season
    if risk_category:
        where_parts.append("risk_category = %(risk_category)s")
        params["risk_category"] = risk_category
    where = " AND ".join(where_parts)
    query = f"SELECT count(*) FROM fct_collision_risk_ml WHERE {where}"
    return fetch_scalar(query, params) or 0


def get_ml_risk_detail(
    h3_cell: int,
    season: str | None = None,
) -> dict[str, Any] | None:
    """Full ML risk detail for a single H3 cell."""
    if season:
        query = "SELECT * FROM fct_collision_risk_ml WHERE h3_cell = %s AND season = %s"
        return fetch_one(query, (h3_cell, season))
    # Return first season if not specified
    query = (
        "SELECT * FROM fct_collision_risk_ml WHERE h3_cell = %s ORDER BY season LIMIT 1"
    )
    return fetch_one(query, (h3_cell,))


def get_ml_risk_stats(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
) -> dict[str, Any] | None:
    """Aggregate ML risk statistics for a bounding box."""
    where_parts = [_BBOX_WHERE_DIRECT]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    if season:
        where_parts.append("season = %(season)s")
        params["season"] = season
    where = " AND ".join(where_parts)

    query = (
        "SELECT "
        "  count(*) AS total_cells, "
        "  avg(risk_score)::float AS avg_risk_score, "
        "  max(risk_score)::float AS max_risk_score, "
        "  min(risk_score)::float AS min_risk_score "
        f"FROM fct_collision_risk_ml WHERE {where}"
    )
    row = fetch_one(query, params)
    if not row or row["total_cells"] == 0:
        return None

    cat_query = (
        "SELECT risk_category, count(*) AS cnt "
        f"FROM fct_collision_risk_ml WHERE {where} "
        "GROUP BY risk_category"
    )
    cat_rows = fetch_all(cat_query, params)
    row["category_counts"] = {r["risk_category"]: r["cnt"] for r in cat_rows}
    return row


# ── Risk breakdown ──────────────────────────────────────────


def get_risk_breakdown(h3_cell: int) -> dict[str, Any] | None:
    """Full risk breakdown for a single cell (all sub-components)."""
    query = "SELECT * FROM fct_collision_risk WHERE h3_cell = %s"
    return fetch_one(query, (h3_cell,))


# ── Risk compare ────────────────────────────────────────────


def get_risk_compare(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Compare standard vs ML risk side-by-side."""
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    params["limit"] = limit
    params["offset"] = offset

    if season:
        params["season"] = season
        query = (
            "SELECT "
            "  s.h3_cell, s.cell_lat, s.cell_lon, "
            "  s.risk_score AS standard_risk_score, "
            "  s.risk_category AS standard_risk_category, "
            "  m.risk_score AS ml_risk_score, "
            "  m.risk_category AS ml_risk_category, "
            "  (m.risk_score - s.risk_score)::float "
            "    AS score_difference "
            "FROM fct_collision_risk_seasonal s "
            "JOIN fct_collision_risk_ml m "
            "  ON s.h3_cell = m.h3_cell "
            "  AND s.season = m.season "
            "WHERE s.cell_lat BETWEEN %(lat_min)s AND %(lat_max)s "
            "  AND s.cell_lon BETWEEN %(lon_min)s AND %(lon_max)s "
            "  AND s.season = %(season)s "
            "ORDER BY abs(m.risk_score - s.risk_score) DESC "
            "LIMIT %(limit)s OFFSET %(offset)s"
        )
    else:
        query = (
            "SELECT "
            "  s.h3_cell, s.cell_lat, s.cell_lon, "
            "  s.risk_score AS standard_risk_score, "
            "  s.risk_category AS standard_risk_category, "
            "  m.risk_score AS ml_risk_score, "
            "  m.risk_category AS ml_risk_category, "
            "  (m.risk_score - s.risk_score)::float "
            "    AS score_difference "
            "FROM fct_collision_risk s "
            "JOIN fct_collision_risk_ml m "
            "  ON s.h3_cell = m.h3_cell "
            "WHERE s.cell_lat BETWEEN %(lat_min)s AND %(lat_max)s "
            "  AND s.cell_lon BETWEEN %(lon_min)s AND %(lon_max)s "
            "ORDER BY abs(m.risk_score - s.risk_score) DESC "
            "LIMIT %(limit)s OFFSET %(offset)s"
        )
    return fetch_all(query, params)


def count_risk_compare(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
) -> int:
    """Count risk compare rows in bbox."""
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    if season:
        params["season"] = season
        query = (
            "SELECT count(*) "
            "FROM fct_collision_risk_seasonal s "
            "JOIN fct_collision_risk_ml m "
            "  ON s.h3_cell = m.h3_cell "
            "  AND s.season = m.season "
            "WHERE s.cell_lat BETWEEN %(lat_min)s AND %(lat_max)s "
            "  AND s.cell_lon BETWEEN %(lon_min)s AND %(lon_max)s "
            "  AND s.season = %(season)s"
        )
    else:
        query = (
            "SELECT count(*) "
            "FROM fct_collision_risk s "
            "JOIN fct_collision_risk_ml m "
            "  ON s.h3_cell = m.h3_cell "
            "WHERE s.cell_lat BETWEEN %(lat_min)s AND %(lat_max)s "
            "  AND s.cell_lon BETWEEN %(lon_min)s AND %(lon_max)s"
        )
    return fetch_scalar(query, params) or 0


# ── Seasonal species ────────────────────────────────────────


def get_seasonal_species(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
    min_sightings: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query seasonal cetacean density within a bounding box."""
    where_parts = [_BBOX_WHERE]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)

    if season:
        where_parts.append("c.season = %(season)s")
        params["season"] = season
    if min_sightings is not None:
        where_parts.append("c.total_sightings >= %(min_sightings)s")
        params["min_sightings"] = min_sightings

    where = " AND ".join(where_parts)
    params["limit"] = limit
    params["offset"] = offset

    query = (
        "SELECT g.h3_cell, g.cell_lat, g.cell_lon, c.season, "
        "  c.total_sightings, c.unique_species, "
        "  c.baleen_whale_sightings AS baleen_sightings, "
        "  c.recent_sightings, "
        "  c.right_whale_sightings, c.humpback_sightings, "
        "  c.fin_whale_sightings, c.blue_whale_sightings, "
        "  c.sperm_whale_sightings, c.minke_whale_sightings "
        "FROM int_hex_grid g "
        "JOIN int_cetacean_density_seasonal c "
        "  ON g.h3_cell = c.h3_cell "
        f"WHERE {where} "
        "ORDER BY c.total_sightings DESC "
        f"LIMIT %(limit)s OFFSET %(offset)s"
    )
    return fetch_all(query, params)


def count_seasonal_species(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
    min_sightings: int | None = None,
) -> int:
    """Count seasonal species rows in bbox."""
    where_parts = [_BBOX_WHERE]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    if season:
        where_parts.append("c.season = %(season)s")
        params["season"] = season
    if min_sightings is not None:
        where_parts.append("c.total_sightings >= %(min_sightings)s")
        params["min_sightings"] = min_sightings
    where = " AND ".join(where_parts)
    query = (
        "SELECT count(*) FROM int_hex_grid g "
        "JOIN int_cetacean_density_seasonal c "
        "  ON g.h3_cell = c.h3_cell "
        f"WHERE {where}"
    )
    return fetch_scalar(query, params) or 0


# ── Seasonal traffic ────────────────────────────────────────


def get_seasonal_traffic(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query seasonal traffic aggregates within a bounding box."""
    where_parts = [_BBOX_WHERE]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)

    if season:
        where_parts.append("t.season = %(season)s")
        params["season"] = season

    where = " AND ".join(where_parts)
    params["limit"] = limit
    params["offset"] = offset

    query = (
        "SELECT g.h3_cell, g.cell_lat, g.cell_lon, t.season, "
        "  t.total_months, t.total_pings, "
        "  t.avg_monthly_vessels, t.avg_speed_knots, "
        "  t.avg_high_speed_fraction, "
        "  t.avg_draft_risk_fraction, "
        "  t.avg_large_vessels, t.avg_commercial_vessels, "
        "  t.avg_fishing_vessels, t.avg_night_fraction "
        "FROM int_hex_grid g "
        "JOIN int_vessel_traffic_seasonal t "
        "  ON g.h3_cell = t.h3_cell "
        f"WHERE {where} "
        "ORDER BY t.avg_monthly_vessels DESC NULLS LAST "
        f"LIMIT %(limit)s OFFSET %(offset)s"
    )
    return fetch_all(query, params)


def count_seasonal_traffic(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
) -> int:
    """Count seasonal traffic rows in bbox."""
    where_parts = [_BBOX_WHERE]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    if season:
        where_parts.append("t.season = %(season)s")
        params["season"] = season
    where = " AND ".join(where_parts)
    query = (
        "SELECT count(*) FROM int_hex_grid g "
        "JOIN int_vessel_traffic_seasonal t "
        "  ON g.h3_cell = t.h3_cell "
        f"WHERE {where}"
    )
    return fetch_scalar(query, params) or 0


# ── Traffic density ─────────────────────────────────────────


def get_traffic_density(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query detailed traffic metrics from int_vessel_traffic_seasonal.

    Returns the 8 composite traffic sub-score inputs plus supporting
    fields so the frontend can render hex cells coloured by any
    danger metric.
    """
    where_parts = [_BBOX_WHERE]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)

    if season:
        where_parts.append("t.season = %(season)s")
        params["season"] = season

    where = " AND ".join(where_parts)
    params["limit"] = limit
    params["offset"] = offset

    query = (
        "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
        "  t.season, "
        "  t.months_active, "
        "  t.total_pings, "
        "  t.avg_monthly_vessels, "
        "  t.avg_speed_knots, "
        "  t.peak_speed_knots, "
        "  t.avg_high_speed_fraction, "
        "  t.avg_speed_lethality, "
        "  t.avg_vessel_length_m, "
        "  t.avg_deep_draft_vessels, "
        "  t.avg_draft_risk_fraction, "
        "  t.avg_large_vessels, "
        "  t.avg_commercial_vessels, "
        "  t.avg_fishing_vessels, "
        "  t.avg_passenger_vessels, "
        "  t.avg_night_vessels, "
        "  t.avg_night_high_speed, "
        "  t.night_traffic_ratio, "
        "  t.avg_cog_diversity, "
        "  t.avg_draft_imputed_m "
        "FROM int_hex_grid g "
        "JOIN int_vessel_traffic_seasonal t "
        "  ON g.h3_cell = t.h3_cell "
        f"WHERE {where} "
        "ORDER BY t.avg_monthly_vessels DESC NULLS LAST "
        f"LIMIT %(limit)s OFFSET %(offset)s"
    )
    return fetch_all(query, params)


def count_traffic_density(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    season: str | None = None,
) -> int:
    """Count traffic density rows in bbox."""
    where_parts = [_BBOX_WHERE]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    if season:
        where_parts.append("t.season = %(season)s")
        params["season"] = season
    where = " AND ".join(where_parts)
    query = (
        "SELECT count(*) FROM int_hex_grid g "
        "JOIN int_vessel_traffic_seasonal t "
        "  ON g.h3_cell = t.h3_cell "
        f"WHERE {where}"
    )
    return fetch_scalar(query, params) or 0
