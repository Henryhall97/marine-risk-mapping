"""Collision risk zone endpoints.

GET /api/v1/risk/zones        — List risk zones within a bounding box
GET /api/v1/risk/zones/stats  — Aggregate statistics for a bounding box
GET /api/v1/risk/zones/{h3}   — Full detail for a single H3 cell
GET /api/v1/risk/seasonal     — Seasonal risk zones within a bounding box
GET /api/v1/risk/ml           — ML-enhanced risk zones
GET /api/v1/risk/ml/stats     — ML risk statistics for a bounding box
GET /api/v1/risk/ml/{h3}      — ML risk detail for a single cell
GET /api/v1/risk/breakdown/{h3} — Full risk breakdown for a cell
GET /api/v1/risk/compare      — Standard vs ML side-by-side
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.config import DEFAULT_PAGE_SIZE, MAX_BBOX_AREA_DEG2, MAX_PAGE_SIZE
from backend.models.layers import (
    MLRiskListResponse,
    MLRiskScores,
    MLRiskStatsResponse,
    MLRiskZoneDetail,
    MLRiskZoneSummary,
    RiskBreakdown,
    RiskCompare,
    RiskCompareListResponse,
    TrafficBreakdown,
)
from backend.models.risk import (
    RiskFlags,
    RiskScores,
    RiskStatsResponse,
    RiskZoneDetail,
    RiskZoneListResponse,
    RiskZoneSummary,
    SeasonalRiskListResponse,
    SeasonalRiskZone,
)
from backend.services import layers as layer_svc
from backend.services import risk as risk_svc

router = APIRouter(prefix="/risk", tags=["risk"])

_VALID_CATEGORIES = {"critical", "high", "medium", "low", "minimal"}
_VALID_SEASONS = {"winter", "spring", "summer", "fall"}


def _validate_bbox(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> None:
    if lat_min >= lat_max:
        raise HTTPException(400, "lat_min must be less than lat_max")
    if lon_min >= lon_max:
        raise HTTPException(400, "lon_min must be less than lon_max")
    area = (lat_max - lat_min) * (lon_max - lon_min)
    if area > MAX_BBOX_AREA_DEG2:
        raise HTTPException(
            400,
            f"Bounding box area ({area:.1f} deg²) exceeds "
            f"maximum ({MAX_BBOX_AREA_DEG2} deg²). "
            "Narrow your query region.",
        )


# ── Static risk zones ──────────────────────────────────────


@router.get("/zones", response_model=RiskZoneListResponse)
def list_risk_zones(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    risk_category: str | None = Query(None),
    min_risk_score: float | None = Query(None, ge=0, le=1),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """List risk zone summaries within a bounding box.

    Returns H3 cell coordinates, risk score, and category.
    Ordered by risk_score descending.
    """
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    if risk_category and risk_category not in _VALID_CATEGORIES:
        raise HTTPException(
            400,
            f"Invalid risk_category. Must be one of: {sorted(_VALID_CATEGORIES)}",
        )

    total = risk_svc.count_risk_zones(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        risk_category=risk_category,
        min_risk_score=min_risk_score,
    )
    rows = risk_svc.get_risk_zones(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        risk_category=risk_category,
        min_risk_score=min_risk_score,
        limit=limit,
        offset=offset,
    )
    data = [RiskZoneSummary(**r) for r in rows]
    return RiskZoneListResponse(total=total, offset=offset, limit=limit, data=data)


@router.get("/zones/stats", response_model=RiskStatsResponse)
def risk_zone_stats(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
):
    """Aggregate risk statistics for a bounding box."""
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    stats = risk_svc.get_risk_stats(lat_min, lat_max, lon_min, lon_max)
    if stats is None:
        raise HTTPException(404, "No risk data found in this bounding box")
    return RiskStatsResponse(**stats)


@router.get("/zones/{h3_cell}", response_model=RiskZoneDetail)
def get_risk_zone(h3_cell: int):
    """Full detail for a single H3 cell."""
    row = risk_svc.get_risk_zone_detail(h3_cell)
    if row is None:
        raise HTTPException(404, f"H3 cell {h3_cell} not found")
    return _row_to_detail(row)


# ── Seasonal risk zones ────────────────────────────────────


@router.get("/seasonal", response_model=SeasonalRiskListResponse)
def list_seasonal_risk(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    season: str | None = Query(None),
    risk_category: str | None = Query(None),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Seasonal risk zones within a bounding box.

    Filter by season (winter/spring/summer/fall) and/or category.
    Scores are season-relative percentile ranks.
    """
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    if season and season not in _VALID_SEASONS:
        raise HTTPException(
            400,
            f"Invalid season. Must be one of: {sorted(_VALID_SEASONS)}",
        )
    if risk_category and risk_category not in _VALID_CATEGORIES:
        raise HTTPException(
            400,
            f"Invalid risk_category. Must be one of: {sorted(_VALID_CATEGORIES)}",
        )

    total = risk_svc.count_seasonal_risk_zones(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        season=season,
        risk_category=risk_category,
    )
    rows = risk_svc.get_seasonal_risk_zones(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        season=season,
        risk_category=risk_category,
        limit=limit,
        offset=offset,
    )
    data = [_row_to_seasonal(r) for r in rows]
    return SeasonalRiskListResponse(total=total, offset=offset, limit=limit, data=data)


# ── Row mapping helpers ─────────────────────────────────────


def _row_to_detail(row: dict) -> RiskZoneDetail:
    """Map a full fct_collision_risk row to the detail model."""
    scores = RiskScores(
        traffic_score=row.get("traffic_score"),
        cetacean_score=row.get("cetacean_score"),
        proximity_score=row.get("proximity_score"),
        strike_score=row.get("strike_score"),
        habitat_score=row.get("habitat_score"),
        protection_gap=row.get("protection_gap"),
        reference_risk_score=row.get("reference_risk_score"),
    )
    flags = RiskFlags(
        has_traffic=row.get("has_traffic", False),
        has_whale_sightings=row.get("has_whale_sightings", False),
        in_mpa=row.get("in_mpa", False),
        has_strike_history=row.get("has_strike_history", False),
        in_speed_zone=row.get("in_speed_zone", False),
        in_current_sma=row.get("in_current_sma", False),
        in_proposed_zone=row.get("in_proposed_zone", False),
        has_nisi_reference=row.get("has_nisi_reference", False),
    )
    return RiskZoneDetail(
        h3_cell=row["h3_cell"],
        cell_lat=row["cell_lat"],
        cell_lon=row["cell_lon"],
        risk_score=float(row["risk_score"]),
        risk_category=row["risk_category"],
        scores=scores,
        flags=flags,
        # Traffic
        months_active=row.get("months_active"),
        total_pings=row.get("total_pings"),
        avg_monthly_vessels=row.get("avg_monthly_vessels"),
        peak_monthly_vessels=row.get("peak_monthly_vessels"),
        avg_speed_knots=row.get("avg_speed_knots"),
        peak_speed_knots=row.get("peak_speed_knots"),
        avg_high_speed_vessels=row.get("avg_high_speed_vessels"),
        avg_large_vessels=row.get("avg_large_vessels"),
        avg_speed_lethality=row.get("avg_speed_lethality"),
        night_traffic_ratio=row.get("night_traffic_ratio"),
        avg_commercial_vessels=row.get("avg_commercial_vessels"),
        avg_fishing_vessels=row.get("avg_fishing_vessels"),
        # Cetacean
        total_sightings=row.get("total_sightings"),
        unique_species=row.get("unique_species"),
        recent_sightings=row.get("recent_sightings"),
        baleen_whale_sightings=row.get("baleen_whale_sightings"),
        # Strike
        total_strikes=row.get("total_strikes"),
        fatal_strikes=row.get("fatal_strikes"),
        strike_species_list=row.get("strike_species_list"),
        # Bathymetry
        depth_m=row.get("depth_m"),
        depth_zone=row.get("depth_zone"),
        is_continental_shelf=row.get("is_continental_shelf"),
        # Ocean
        sst=row.get("sst"),
        mld=row.get("mld"),
        pp_upper_200m=row.get("pp_upper_200m"),
        # Proximity
        dist_to_nearest_whale_km=row.get("dist_to_nearest_whale_km"),
        dist_to_nearest_ship_km=row.get("dist_to_nearest_ship_km"),
        dist_to_nearest_strike_km=row.get("dist_to_nearest_strike_km"),
        dist_to_nearest_protection_km=row.get("dist_to_nearest_protection_km"),
        # MPA
        mpa_count=row.get("mpa_count"),
        has_strict_protection=row.get("has_strict_protection"),
        # Speed zone
        zone_count=row.get("zone_count"),
        zone_names=row.get("zone_names"),
        # Nisi
        nisi_all_risk=row.get("nisi_all_risk"),
    )


def _row_to_seasonal(row: dict) -> SeasonalRiskZone:
    """Map a seasonal risk row to the response model."""
    scores = RiskScores(
        traffic_score=row.get("traffic_score"),
        cetacean_score=row.get("cetacean_score"),
        proximity_score=row.get("proximity_score"),
        strike_score=row.get("strike_score"),
        habitat_score=row.get("habitat_score"),
        protection_gap=row.get("protection_gap"),
        reference_risk_score=row.get("reference_risk_score"),
    )
    flags = RiskFlags(
        has_traffic=row.get("has_traffic", False),
        has_whale_sightings=row.get("has_whale_sightings", False),
        in_mpa=row.get("in_mpa", False),
        has_strike_history=row.get("has_strike_history", False),
        in_speed_zone=row.get("in_speed_zone", False),
        in_current_sma=row.get("in_current_sma", False),
        in_proposed_zone=row.get("in_proposed_zone", False),
        has_nisi_reference=row.get("has_nisi_reference", False),
    )
    return SeasonalRiskZone(
        h3_cell=row["h3_cell"],
        season=row["season"],
        cell_lat=row["cell_lat"],
        cell_lon=row["cell_lon"],
        risk_score=float(row["risk_score"]),
        risk_category=row["risk_category"],
        scores=scores,
        flags=flags,
    )


# ── ML-enhanced risk zones ─────────────────────────────────


@router.get("/ml", response_model=MLRiskListResponse)
def list_ml_risk_zones(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    season: str | None = Query(None),
    risk_category: str | None = Query(None),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """ML-enhanced risk zones (ISDM-based) within a bounding box.

    Uses fct_collision_risk_ml. Season filter required for
    seasonal data; omit for all seasons.
    """
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    if season and season not in _VALID_SEASONS:
        raise HTTPException(
            400,
            f"Invalid season. Must be one of: {sorted(_VALID_SEASONS)}",
        )
    if risk_category and risk_category not in _VALID_CATEGORIES:
        raise HTTPException(
            400,
            f"Invalid risk_category. Must be one of: {sorted(_VALID_CATEGORIES)}",
        )
    total = layer_svc.count_ml_risk_zones(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        season=season,
        risk_category=risk_category,
    )
    rows = layer_svc.get_ml_risk_zones(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        season=season,
        risk_category=risk_category,
        limit=limit,
        offset=offset,
    )
    data = [MLRiskZoneSummary(**r) for r in rows]
    return MLRiskListResponse(total=total, offset=offset, limit=limit, data=data)


@router.get("/ml/stats", response_model=MLRiskStatsResponse)
def ml_risk_stats(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    season: str | None = Query(None),
):
    """Aggregate ML risk statistics for a bounding box."""
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    if season and season not in _VALID_SEASONS:
        raise HTTPException(
            400,
            f"Invalid season. Must be one of: {sorted(_VALID_SEASONS)}",
        )
    stats = layer_svc.get_ml_risk_stats(
        lat_min, lat_max, lon_min, lon_max, season=season
    )
    if stats is None:
        raise HTTPException(404, "No ML risk data found in this bounding box")
    return MLRiskStatsResponse(**stats)


@router.get("/ml/{h3_cell}", response_model=MLRiskZoneDetail)
def get_ml_risk_zone(
    h3_cell: int,
    season: str | None = Query(None),
):
    """Full ML risk detail for a single H3 cell."""
    if season and season not in _VALID_SEASONS:
        raise HTTPException(
            400,
            f"Invalid season. Must be one of: {sorted(_VALID_SEASONS)}",
        )
    row = layer_svc.get_ml_risk_detail(h3_cell, season=season)
    if row is None:
        raise HTTPException(404, f"H3 cell {h3_cell} not found in ML mart")
    return _row_to_ml_detail(row)


# ── Risk breakdown ──────────────────────────────────────────


@router.get("/breakdown/{h3_cell}", response_model=RiskBreakdown)
def risk_breakdown(h3_cell: int):
    """Full risk breakdown for a single H3 cell.

    Explains WHY a cell has its risk score — shows all sub-score
    components including traffic breakdown, cetacean counts,
    proximity distances, habitat, and protection status.
    """
    row = layer_svc.get_risk_breakdown(h3_cell)
    if row is None:
        raise HTTPException(404, f"H3 cell {h3_cell} not found")
    return _row_to_breakdown(row)


# ── Risk compare ────────────────────────────────────────────


@router.get("/compare", response_model=RiskCompareListResponse)
def compare_risk(
    lat_min: float = Query(..., ge=-90, le=90),
    lat_max: float = Query(..., ge=-90, le=90),
    lon_min: float = Query(..., ge=-180, le=180),
    lon_max: float = Query(..., ge=-180, le=180),
    season: str | None = Query(None),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Compare standard vs ML risk scores side-by-side.

    Ordered by absolute score difference (biggest disagreements first).
    Without season: compares static marts.
    With season: compares seasonal vs ML at that season.
    """
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)
    if season and season not in _VALID_SEASONS:
        raise HTTPException(
            400,
            f"Invalid season. Must be one of: {sorted(_VALID_SEASONS)}",
        )
    total = layer_svc.count_risk_compare(
        lat_min, lat_max, lon_min, lon_max, season=season
    )
    rows = layer_svc.get_risk_compare(
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        season=season,
        limit=limit,
        offset=offset,
    )
    data = [RiskCompare(**r) for r in rows]
    return RiskCompareListResponse(total=total, offset=offset, limit=limit, data=data)


# ── ML detail helper ────────────────────────────────────────


def _row_to_ml_detail(row: dict) -> MLRiskZoneDetail:
    """Map an fct_collision_risk_ml row to the detail model."""
    scores = MLRiskScores(
        whale_traffic_interaction=row.get("whale_traffic_interaction_score"),
        traffic_score=row.get("traffic_score"),
        whale_ml_exposure=row.get("whale_ml_exposure_score"),
        proximity_score=row.get("proximity_score"),
        strike_score=row.get("strike_score"),
        protection_gap=row.get("protection_gap"),
        reference_risk_score=row.get("reference_risk_score"),
    )
    return MLRiskZoneDetail(
        h3_cell=row["h3_cell"],
        season=row.get("season"),
        cell_lat=row["cell_lat"],
        cell_lon=row["cell_lon"],
        risk_score=float(row["risk_score"]),
        risk_category=row["risk_category"],
        scores=scores,
        any_whale_prob=row.get("any_whale_prob"),
        max_whale_prob=row.get("max_whale_prob"),
        mean_whale_prob=row.get("mean_whale_prob"),
        isdm_blue_whale=row.get("isdm_blue_whale"),
        isdm_fin_whale=row.get("isdm_fin_whale"),
        isdm_humpback_whale=row.get("isdm_humpback_whale"),
        isdm_sperm_whale=row.get("isdm_sperm_whale"),
    )


# ── Breakdown helper ────────────────────────────────────────


def _row_to_breakdown(row: dict) -> RiskBreakdown:
    """Map an fct_collision_risk row to breakdown model."""
    traffic = TrafficBreakdown(
        traffic_score=row.get("traffic_score"),
        pctl_vessels=row.get("pctl_vessels"),
        pctl_speed_lethality=row.get("pctl_speed_lethality"),
        pctl_large_vessels=row.get("pctl_large_vessels"),
        pctl_draft_risk=row.get("pctl_draft_risk"),
        pctl_high_speed_fraction=row.get("pctl_high_speed_fraction"),
        pctl_draft_risk_fraction=row.get("pctl_draft_risk_fraction"),
        pctl_commercial=row.get("pctl_commercial"),
        pctl_night_traffic=row.get("pctl_night_traffic"),
    )
    return RiskBreakdown(
        h3_cell=row["h3_cell"],
        cell_lat=row["cell_lat"],
        cell_lon=row["cell_lon"],
        risk_score=float(row["risk_score"]),
        risk_category=row["risk_category"],
        traffic=traffic,
        cetacean_score=row.get("cetacean_score"),
        total_sightings=row.get("total_sightings"),
        unique_species=row.get("unique_species"),
        proximity_score=row.get("proximity_score"),
        dist_to_nearest_whale_km=row.get("dist_to_nearest_whale_km"),
        dist_to_nearest_ship_km=row.get("dist_to_nearest_ship_km"),
        strike_score=row.get("strike_score"),
        total_strikes=row.get("total_strikes"),
        habitat_score=row.get("habitat_score"),
        depth_m=row.get("depth_m"),
        depth_zone=row.get("depth_zone"),
        sst=row.get("sst"),
        pp_upper_200m=row.get("pp_upper_200m"),
        protection_gap=row.get("protection_gap"),
        mpa_count=row.get("mpa_count"),
        in_speed_zone=row.get("in_speed_zone"),
        reference_risk_score=row.get("reference_risk_score"),
        nisi_all_risk=row.get("nisi_all_risk"),
    )
