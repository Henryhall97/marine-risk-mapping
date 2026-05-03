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
    scenario: str | None = None,
    decade: str | None = None,
    mode: str = "absolute",
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query ocean covariates — annual mean, single season, or projected.

    When *mode* = ``"change"`` and projecting, joins against the
    current seasonal baseline to return delta columns
    (``delta_sst``, ``delta_mld``, etc.) alongside absolute values.
    """
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    params["limit"] = limit
    params["offset"] = offset

    # ── Climate projection mode ──────────────────────────
    if scenario and decade:
        where_parts = [_BBOX_WHERE]
        params["scenario"] = scenario
        params["decade"] = decade
        where_parts.append("o.scenario = %(scenario)s")
        where_parts.append("o.decade = %(decade)s")
        if season and season != "all":
            params["season"] = season
            where_parts.append("o.season = %(season)s")
        where = " AND ".join(where_parts)

        if mode == "change":
            query = (
                "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
                "  o.season, o.scenario, o.decade, "
                "  o.sst, o.sst_sd, o.mld, "
                "  o.sla, o.pp_upper_200m, "
                "  (o.sst - coalesce(b.sst, 0)) AS delta_sst, "
                "  (o.sst_sd - coalesce(b.sst_sd, 0))"
                "    AS delta_sst_sd, "
                "  (o.mld - coalesce(b.mld, 0)) AS delta_mld, "
                "  (o.sla - coalesce(b.sla, 0)) AS delta_sla, "
                "  (o.pp_upper_200m"
                "    - coalesce(b.pp_upper_200m, 0))"
                "    AS delta_pp "
                "FROM int_hex_grid g "
                "JOIN int_ocean_covariates_projected o "
                "  ON g.h3_cell = o.h3_cell "
                "LEFT JOIN int_ocean_covariates_seasonal b "
                "  ON o.h3_cell = b.h3_cell "
                "  AND o.season = b.season "
                f"WHERE {where} "
                "ORDER BY o.sst DESC NULLS LAST "
                f"LIMIT %(limit)s OFFSET %(offset)s"
            )
        else:
            query = (
                "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
                "  o.season, o.scenario, o.decade, "
                "  o.sst, o.sst_sd, o.mld, "
                "  o.sla, o.pp_upper_200m "
                "FROM int_hex_grid g "
                "JOIN int_ocean_covariates_projected o "
                "  ON g.h3_cell = o.h3_cell "
                f"WHERE {where} "
                "ORDER BY o.sst DESC NULLS LAST "
                f"LIMIT %(limit)s OFFSET %(offset)s"
            )
        return fetch_all(query, params)

    # ── Current data modes ───────────────────────────────
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
    scenario: str | None = None,
    decade: str | None = None,
) -> int:
    """Count ocean covariate rows in bbox."""
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)

    # ── Climate projection mode ──────────────────────────
    if scenario and decade:
        where_parts = [_BBOX_WHERE]
        params["scenario"] = scenario
        params["decade"] = decade
        where_parts.append("o.scenario = %(scenario)s")
        where_parts.append("o.decade = %(decade)s")
        if season and season != "all":
            params["season"] = season
            where_parts.append("o.season = %(season)s")
        where = " AND ".join(where_parts)
        query = (
            "SELECT count(*) FROM int_hex_grid g "
            "JOIN int_ocean_covariates_projected o "
            "  ON g.h3_cell = o.h3_cell "
            f"WHERE {where}"
        )
        return fetch_scalar(query, params) or 0

    # ── Current data modes ───────────────────────────────
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
        "  s.sdm_right_whale, s.sdm_minke_whale, "
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


# ── Cell context (species + habitat) ───────────────────────


def get_cell_context(
    h3_cell: int,
    season: str | None = None,
) -> dict[str, Any]:
    """Species predictions + BIA/critical habitat for one H3 cell.

    Returns whale predictions (ISDM), cetacean sighting species,
    and whether the cell intersects any BIA or critical habitat polygon.
    """
    result: dict[str, Any] = {"h3_cell": h3_cell}

    # ── ISDM whale predictions ──
    if season:
        isdm = fetch_one(
            "SELECT isdm_blue_whale, isdm_fin_whale, "
            "  isdm_humpback_whale, isdm_sperm_whale, "
            "  any_whale_prob, max_whale_prob, mean_whale_prob "
            "FROM int_ml_whale_predictions "
            "WHERE h3_cell = %s AND season = %s",
            (h3_cell, season),
        )
    else:
        isdm = fetch_one(
            "SELECT isdm_blue_whale, isdm_fin_whale, "
            "  isdm_humpback_whale, isdm_sperm_whale, "
            "  any_whale_prob, max_whale_prob, mean_whale_prob "
            "FROM int_ml_whale_predictions "
            "WHERE h3_cell = %s ORDER BY any_whale_prob DESC "
            "LIMIT 1",
            (h3_cell,),
        )
    if isdm:
        result.update(isdm)
    else:
        result.update(
            isdm_blue_whale=None,
            isdm_fin_whale=None,
            isdm_humpback_whale=None,
            isdm_sperm_whale=None,
            any_whale_prob=None,
            max_whale_prob=None,
            mean_whale_prob=None,
        )

    # ── Cetacean sighting species list (common names via crosswalk) ──
    spp = fetch_one(
        "SELECT string_agg("
        "  DISTINCT COALESCE(xw.common_name, s.species), ', ' "
        "  ORDER BY COALESCE(xw.common_name, s.species)"
        ") AS species_observed "
        "FROM cetacean_sighting_h3 h "
        "JOIN cetacean_sightings s ON h.sighting_id = s.id "
        "LEFT JOIN species_crosswalk xw "
        "  ON lower(s.species) = lower(xw.scientific_name) "
        "WHERE h.h3_cell = %s AND s.species IS NOT NULL "
        "  AND s.species != 'NaN'",
        (h3_cell,),
    )
    result["species_observed"] = spp["species_observed"] if spp else None

    # ── BIAs intersecting this cell's centroid ──
    bias = fetch_all(
        "SELECT b.cmn_name, b.bia_type "
        "FROM cetacean_bia b "
        "JOIN int_hex_grid g ON ST_Intersects("
        "  b.geom, "
        "  ST_SetSRID("
        "    ST_MakePoint(g.cell_lon, g.cell_lat), 4326"
        "  )"
        ") "
        "WHERE g.h3_cell = %s",
        (h3_cell,),
    )
    result["bia_zones"] = [
        {"species": r["cmn_name"], "type": r["bia_type"]} for r in bias
    ]

    # ── Critical habitat intersecting this cell ──
    ch = fetch_all(
        "SELECT c.cmn_name, c.list_status "
        "FROM whale_critical_habitat c "
        "JOIN int_hex_grid g ON ST_Intersects("
        "  c.geom, "
        "  ST_SetSRID("
        "    ST_MakePoint(g.cell_lon, g.cell_lat), 4326"
        "  )"
        ") "
        "WHERE g.h3_cell = %s",
        (h3_cell,),
    )
    result["critical_habitat"] = [
        {"species": r["cmn_name"], "status": r["list_status"]} for r in ch
    ]

    return result


# ── SDM projections (CMIP6 climate) ────────────────────────


def get_sdm_projections(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    scenario: str,
    decade: str,
    season: str | None = None,
    species: str | None = None,
    min_probability: float | None = None,
    mode: str = "absolute",
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query SDM projections under CMIP6 scenarios.

    When *mode* = ``"change"``, joins against the baseline
    ``ml_sdm_predictions`` table and returns delta columns
    (``delta_any_whale``, etc.) alongside absolute values.
    """
    where_parts = [
        _BBOX_WHERE,
        "p.scenario = %(scenario)s",
        "p.decade = %(decade)s",
    ]
    params = _bbox_params(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        scenario=scenario,
        decade=decade,
    )

    if season:
        where_parts.append("p.season = %(season)s")
        params["season"] = season

    if species and min_probability is not None:
        col = f"p.sdm_{species}"
        where_parts.append(f"{col} >= %(min_prob)s")
        params["min_prob"] = min_probability
    elif min_probability is not None:
        where_parts.append("p.sdm_any_whale >= %(min_prob)s")
        params["min_prob"] = min_probability

    where = " AND ".join(where_parts)
    params["limit"] = limit
    params["offset"] = offset

    if mode == "change":
        query = (
            "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
            "  p.season, p.scenario, p.decade, "
            "  p.sdm_any_whale, "
            "  p.sdm_blue_whale, p.sdm_fin_whale, "
            "  p.sdm_humpback_whale, p.sdm_sperm_whale, "
            "  p.sdm_right_whale, p.sdm_minke_whale, "
            "  (p.sdm_any_whale - coalesce(b.sdm_any_whale, 0))"
            "    AS delta_any_whale, "
            "  (p.sdm_blue_whale - coalesce(b.sdm_blue_whale, 0))"
            "    AS delta_blue_whale, "
            "  (p.sdm_fin_whale - coalesce(b.sdm_fin_whale, 0))"
            "    AS delta_fin_whale, "
            "  (p.sdm_humpback_whale"
            "    - coalesce(b.sdm_humpback_whale, 0))"
            "    AS delta_humpback_whale, "
            "  (p.sdm_sperm_whale"
            "    - coalesce(b.sdm_sperm_whale, 0))"
            "    AS delta_sperm_whale, "
            "  (p.sdm_right_whale"
            "    - coalesce(b.sdm_right_whale, 0))"
            "    AS delta_right_whale, "
            "  (p.sdm_minke_whale"
            "    - coalesce(b.sdm_minke_whale, 0))"
            "    AS delta_minke_whale "
            "FROM int_hex_grid g "
            "JOIN whale_sdm_projections p "
            "  ON g.h3_cell = p.h3_cell "
            "LEFT JOIN ml_sdm_predictions b "
            "  ON p.h3_cell = b.h3_cell "
            "  AND p.season = b.season "
            f"WHERE {where} "
            "ORDER BY p.sdm_any_whale DESC "
            f"LIMIT %(limit)s OFFSET %(offset)s"
        )
    else:
        query = (
            "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
            "  p.season, p.scenario, p.decade, "
            "  p.sdm_any_whale, "
            "  p.sdm_blue_whale, p.sdm_fin_whale, "
            "  p.sdm_humpback_whale, p.sdm_sperm_whale, "
            "  p.sdm_right_whale, p.sdm_minke_whale "
            "FROM int_hex_grid g "
            "JOIN whale_sdm_projections p "
            "  ON g.h3_cell = p.h3_cell "
            f"WHERE {where} "
            "ORDER BY p.sdm_any_whale DESC "
            f"LIMIT %(limit)s OFFSET %(offset)s"
        )
    return fetch_all(query, params)


def count_sdm_projections(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    scenario: str,
    decade: str,
    season: str | None = None,
    species: str | None = None,
    min_probability: float | None = None,
) -> int:
    """Count SDM projection rows in bbox."""
    where_parts = [
        _BBOX_WHERE,
        "p.scenario = %(scenario)s",
        "p.decade = %(decade)s",
    ]
    params = _bbox_params(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        scenario=scenario,
        decade=decade,
    )

    if season:
        where_parts.append("p.season = %(season)s")
        params["season"] = season

    if species and min_probability is not None:
        col = f"p.sdm_{species}"
        where_parts.append(f"{col} >= %(min_prob)s")
        params["min_prob"] = min_probability
    elif min_probability is not None:
        where_parts.append("p.sdm_any_whale >= %(min_prob)s")
        params["min_prob"] = min_probability

    where = " AND ".join(where_parts)
    query = (
        "SELECT count(*) FROM int_hex_grid g "
        "JOIN whale_sdm_projections p "
        "  ON g.h3_cell = p.h3_cell "
        f"WHERE {where}"
    )
    return fetch_scalar(query, params) or 0


def get_projection_summary(
    lat_min: float | None,
    lat_max: float | None,
    lon_min: float | None,
    lon_max: float | None,
    species: str | None = None,
) -> list[dict[str, Any]]:
    """Summarise projected habitat change across scenarios/decades.

    Returns one row per (scenario, decade, season) with mean
    and high-probability cell counts for a given species (or
    any_whale by default).  Bbox is optional — omit for
    coast-wide summary.
    """
    col = f"sdm_{species}" if species else "sdm_any_whale"
    has_bbox = all(v is not None for v in (lat_min, lat_max, lon_min, lon_max))

    if has_bbox:
        params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
        query = (
            "SELECT p.scenario, p.decade, p.season, "
            f"  count(*) as cell_count, "
            f"  avg(p.{col}) as mean_prob, "
            f"  percentile_cont(0.5) "
            f"    WITHIN GROUP (ORDER BY p.{col}) as median_prob, "
            f"  count(*) FILTER "
            f"    (WHERE p.{col} > 0.5) as high_prob_cells, "
            f"  max(p.{col}) as max_prob "
            "FROM int_hex_grid g "
            "JOIN whale_sdm_projections p "
            "  ON g.h3_cell = p.h3_cell "
            f"WHERE {_BBOX_WHERE} "
            "GROUP BY p.scenario, p.decade, p.season "
            "ORDER BY p.scenario, p.decade, p.season"
        )
    else:
        params: dict[str, Any] = {}
        query = (
            "SELECT scenario, decade, season, "
            f"  count(*) as cell_count, "
            f"  avg({col}) as mean_prob, "
            f"  percentile_cont(0.5) "
            f"    WITHIN GROUP (ORDER BY {col}) as median_prob, "
            f"  count(*) FILTER "
            f"    (WHERE {col} > 0.5) as high_prob_cells, "
            f"  max({col}) as max_prob "
            "FROM whale_sdm_projections "
            "GROUP BY scenario, decade, season "
            "ORDER BY scenario, decade, season"
        )
    return fetch_all(query, params)


# ── ISDM projections (CMIP6 climate) ──────────────────────


def get_isdm_projections(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    scenario: str,
    decade: str,
    season: str | None = None,
    species: str | None = None,
    min_probability: float | None = None,
    mode: str = "absolute",
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query ISDM projections under CMIP6 scenarios.

    When *mode* = ``"change"``, joins against the baseline
    ``ml_whale_predictions`` table and returns delta columns.
    """
    where_parts = [
        _BBOX_WHERE,
        "p.scenario = %(scenario)s",
        "p.decade = %(decade)s",
    ]
    params = _bbox_params(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        scenario=scenario,
        decade=decade,
    )

    if season:
        where_parts.append("p.season = %(season)s")
        params["season"] = season

    if species and min_probability is not None:
        col = f"p.isdm_{species}"
        where_parts.append(f"{col} >= %(min_prob)s")
        params["min_prob"] = min_probability
    elif min_probability is not None:
        where_parts.append(
            "greatest("
            "  coalesce(p.isdm_blue_whale, 0),"
            "  coalesce(p.isdm_fin_whale, 0),"
            "  coalesce(p.isdm_humpback_whale, 0),"
            "  coalesce(p.isdm_sperm_whale, 0)"
            ") >= %(min_prob)s"
        )
        params["min_prob"] = min_probability

    where = " AND ".join(where_parts)
    params["limit"] = limit
    params["offset"] = offset

    if mode == "change":
        query = (
            "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
            "  p.season, p.scenario, p.decade, "
            "  p.isdm_blue_whale, p.isdm_fin_whale, "
            "  p.isdm_humpback_whale, p.isdm_sperm_whale, "
            "  (p.isdm_blue_whale"
            "    - coalesce(b.isdm_blue_whale, 0))"
            "    AS delta_blue_whale, "
            "  (p.isdm_fin_whale"
            "    - coalesce(b.isdm_fin_whale, 0))"
            "    AS delta_fin_whale, "
            "  (p.isdm_humpback_whale"
            "    - coalesce(b.isdm_humpback_whale, 0))"
            "    AS delta_humpback_whale, "
            "  (p.isdm_sperm_whale"
            "    - coalesce(b.isdm_sperm_whale, 0))"
            "    AS delta_sperm_whale "
            "FROM int_hex_grid g "
            "JOIN whale_isdm_projections p "
            "  ON g.h3_cell = p.h3_cell "
            "LEFT JOIN ml_whale_predictions b "
            "  ON p.h3_cell = b.h3_cell "
            "  AND p.season = b.season "
            f"WHERE {where} "
            "ORDER BY greatest("
            "  coalesce(p.isdm_blue_whale, 0),"
            "  coalesce(p.isdm_fin_whale, 0),"
            "  coalesce(p.isdm_humpback_whale, 0),"
            "  coalesce(p.isdm_sperm_whale, 0)"
            ") DESC "
            f"LIMIT %(limit)s OFFSET %(offset)s"
        )
    else:
        query = (
            "SELECT g.h3_cell, g.cell_lat, g.cell_lon, "
            "  p.season, p.scenario, p.decade, "
            "  p.isdm_blue_whale, p.isdm_fin_whale, "
            "  p.isdm_humpback_whale, p.isdm_sperm_whale "
            "FROM int_hex_grid g "
            "JOIN whale_isdm_projections p "
            "  ON g.h3_cell = p.h3_cell "
            f"WHERE {where} "
            "ORDER BY greatest("
            "  coalesce(p.isdm_blue_whale, 0),"
            "  coalesce(p.isdm_fin_whale, 0),"
            "  coalesce(p.isdm_humpback_whale, 0),"
            "  coalesce(p.isdm_sperm_whale, 0)"
            ") DESC "
            f"LIMIT %(limit)s OFFSET %(offset)s"
        )
    return fetch_all(query, params)


def count_isdm_projections(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    scenario: str,
    decade: str,
    season: str | None = None,
    species: str | None = None,
    min_probability: float | None = None,
) -> int:
    """Count ISDM projection rows in bbox."""
    where_parts = [
        _BBOX_WHERE,
        "p.scenario = %(scenario)s",
        "p.decade = %(decade)s",
    ]
    params = _bbox_params(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        scenario=scenario,
        decade=decade,
    )

    if season:
        where_parts.append("p.season = %(season)s")
        params["season"] = season

    if species and min_probability is not None:
        col = f"p.isdm_{species}"
        where_parts.append(f"{col} >= %(min_prob)s")
        params["min_prob"] = min_probability
    elif min_probability is not None:
        where_parts.append(
            "greatest("
            "  coalesce(p.isdm_blue_whale, 0),"
            "  coalesce(p.isdm_fin_whale, 0),"
            "  coalesce(p.isdm_humpback_whale, 0),"
            "  coalesce(p.isdm_sperm_whale, 0)"
            ") >= %(min_prob)s"
        )
        params["min_prob"] = min_probability

    where = " AND ".join(where_parts)
    query = (
        "SELECT count(*) FROM int_hex_grid g "
        "JOIN whale_isdm_projections p "
        "  ON g.h3_cell = p.h3_cell "
        f"WHERE {where}"
    )
    return fetch_scalar(query, params) or 0


# ── Projected ML risk (CMIP6 climate) ──────────────────────


def get_projected_ml_risk(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    scenario: str,
    decade: str,
    mode: str = "absolute",
    season: str | None = None,
    risk_category: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query projected ML risk within a bounding box.

    mode='change' joins against fct_collision_risk_ml to compute
    deltas for risk_score, interaction_score, and whale_ml_score.
    """
    # Use p.-qualified bbox for change mode (JOIN makes bare cols ambiguous)
    _P_BBOX = (
        "p.cell_lat BETWEEN %(lat_min)s AND %(lat_max)s "
        "AND p.cell_lon BETWEEN %(lon_min)s AND %(lon_max)s"
    )
    where_parts = [_P_BBOX if mode == "change" else _BBOX_WHERE_DIRECT]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    params["scenario"] = scenario
    params["decade"] = decade
    where_parts.append("p.scenario = %(scenario)s")
    where_parts.append("p.decade = %(decade)s")

    if season:
        where_parts.append("p.season = %(season)s")
        params["season"] = season
    if risk_category:
        where_parts.append("p.risk_category = %(risk_category)s")
        params["risk_category"] = risk_category

    params["limit"] = limit
    params["offset"] = offset
    where = " AND ".join(where_parts)

    if mode == "change":
        query = (
            "SELECT p.h3_cell, p.cell_lat, p.cell_lon, "
            "  p.season, p.scenario, p.decade, "
            "  p.risk_score, p.risk_category, "
            "  p.interaction_score, p.traffic_score, "
            "  p.whale_ml_score, "
            "  p.strike_score, p.protection_gap, "
            "  p.reference_risk_score, "
            "  p.any_whale_prob, "
            "  p.blue_whale_prob, p.fin_whale_prob, "
            "  p.humpback_whale_prob, p.sperm_whale_prob, "
            "  p.right_whale_prob, p.minke_whale_prob, "
            "  (p.risk_score - c.risk_score) "
            "    AS delta_risk_score, "
            "  (p.interaction_score - c.interaction_score) "
            "    AS delta_interaction_score, "
            "  (p.whale_ml_score - c.whale_ml_score) "
            "    AS delta_whale_ml_score "
            "FROM fct_collision_risk_ml_projected p "
            "LEFT JOIN fct_collision_risk_ml c "
            "  ON p.h3_cell = c.h3_cell "
            "  AND p.season = c.season "
            f"WHERE {where} "
            "ORDER BY p.risk_score DESC "
            "LIMIT %(limit)s OFFSET %(offset)s"
        )
    else:
        query = (
            "SELECT h3_cell, cell_lat, cell_lon, "
            "  season, scenario, decade, "
            "  risk_score, risk_category, "
            "  interaction_score, traffic_score, "
            "  whale_ml_score, "
            "  strike_score, protection_gap, "
            "  reference_risk_score, "
            "  any_whale_prob, "
            "  blue_whale_prob, fin_whale_prob, "
            "  humpback_whale_prob, sperm_whale_prob, "
            "  right_whale_prob, minke_whale_prob "
            "FROM fct_collision_risk_ml_projected p "
            f"WHERE {where} "
            "ORDER BY risk_score DESC "
            "LIMIT %(limit)s OFFSET %(offset)s"
        )
    return fetch_all(query, params)


def count_projected_ml_risk(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    scenario: str,
    decade: str,
    season: str | None = None,
    risk_category: str | None = None,
) -> int:
    """Count projected risk rows matching filters."""
    where_parts = [_BBOX_WHERE_DIRECT]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    params["scenario"] = scenario
    params["decade"] = decade
    where_parts.append("scenario = %(scenario)s")
    where_parts.append("decade = %(decade)s")
    if season:
        where_parts.append("season = %(season)s")
        params["season"] = season
    if risk_category:
        where_parts.append("risk_category = %(risk_category)s")
        params["risk_category"] = risk_category
    where = " AND ".join(where_parts)
    query = f"SELECT count(*) FROM fct_collision_risk_ml_projected WHERE {where}"
    return fetch_scalar(query, params) or 0


def get_projected_ml_risk_stats(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    scenario: str,
    decade: str,
    season: str | None = None,
) -> dict[str, Any] | None:
    """Aggregate projected risk statistics for a bbox."""
    _P_BBOX = (
        "p.cell_lat BETWEEN %(lat_min)s AND %(lat_max)s "
        "AND p.cell_lon BETWEEN %(lon_min)s AND %(lon_max)s"
    )
    where_parts = [_P_BBOX]
    params = _bbox_params(lat_min, lat_max, lon_min, lon_max)
    params["scenario"] = scenario
    params["decade"] = decade
    where_parts.append("p.scenario = %(scenario)s")
    where_parts.append("p.decade = %(decade)s")
    if season:
        where_parts.append("p.season = %(season)s")
        params["season"] = season
    where = " AND ".join(where_parts)

    query = (
        "SELECT "
        "  count(*) AS total_cells, "
        "  avg(p.risk_score)::float AS avg_risk_score, "
        "  max(p.risk_score)::float AS max_risk_score, "
        "  min(p.risk_score)::float AS min_risk_score, "
        "  avg(c.risk_score)::float AS avg_current_risk_score, "
        "  avg(p.risk_score - c.risk_score)::float "
        "    AS avg_delta_risk_score "
        "FROM fct_collision_risk_ml_projected p "
        "LEFT JOIN fct_collision_risk_ml c "
        "  ON p.h3_cell = c.h3_cell "
        "  AND p.season = c.season "
        f"WHERE {where}"
    )
    row = fetch_one(query, params)
    if not row or row.get("total_cells", 0) == 0:
        return None

    # Category breakdown
    cat_query = (
        "SELECT risk_category, count(*) AS cnt "
        "FROM fct_collision_risk_ml_projected p "
        f"WHERE {where} "
        "GROUP BY risk_category"
    )
    cat_rows = fetch_all(cat_query, params)
    cats = {r["risk_category"]: r["cnt"] for r in cat_rows}

    return {**row, "category_counts": cats}
