"""Pydantic schemas for collision risk endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RiskScores(BaseModel):
    """The 7 sub-scores that compose the collision risk score."""

    traffic_score: float | None = None
    cetacean_score: float | None = None
    proximity_score: float | None = None
    strike_score: float | None = None
    habitat_score: float | None = None
    protection_gap: float | None = None
    reference_risk_score: float | None = None


class RiskFlags(BaseModel):
    """Boolean feature flags for a risk cell."""

    has_traffic: bool = False
    has_whale_sightings: bool = False
    in_mpa: bool = False
    has_strike_history: bool = False
    in_speed_zone: bool = False
    in_current_sma: bool = False
    in_proposed_zone: bool = False
    has_nisi_reference: bool = False


class RiskZoneSummary(BaseModel):
    """Compact risk representation for map tiles / list views."""

    h3_cell: int
    cell_lat: float
    cell_lon: float
    risk_score: float
    risk_category: str


class RiskZoneDetail(RiskZoneSummary):
    """Full risk detail for a single H3 cell.

    Extends the summary with sub-scores, flags, traffic features,
    cetacean features, strike history, bathymetry, and ocean data.
    """

    # Sub-scores
    scores: RiskScores

    # Feature flags
    flags: RiskFlags

    # Traffic features (nullable — no traffic → None)
    months_active: int | None = None
    total_pings: int | None = None
    avg_monthly_vessels: float | None = None
    peak_monthly_vessels: float | None = None
    avg_speed_knots: float | None = None
    peak_speed_knots: float | None = None
    avg_high_speed_vessels: float | None = None
    avg_large_vessels: float | None = None
    avg_speed_lethality: float | None = None
    night_traffic_ratio: float | None = None
    avg_commercial_vessels: float | None = None
    avg_fishing_vessels: float | None = None

    # Cetacean features
    total_sightings: int | None = None
    unique_species: int | None = None
    recent_sightings: int | None = None
    baleen_whale_sightings: int | None = None

    # Strike history
    total_strikes: int | None = None
    fatal_strikes: int | None = None
    strike_species_list: str | None = None

    # Bathymetry
    depth_m: float | None = None
    depth_zone: str | None = None
    is_continental_shelf: bool | None = None

    # Ocean covariates
    sst: float | None = None
    sst_sd: float | None = None
    mld: float | None = None
    sla: float | None = None
    pp_upper_200m: float | None = None

    # Proximity
    dist_to_nearest_whale_km: float | None = None
    dist_to_nearest_ship_km: float | None = None
    dist_to_nearest_strike_km: float | None = None
    dist_to_nearest_protection_km: float | None = None

    # MPA
    mpa_count: int | None = None
    has_strict_protection: bool | None = None

    # Speed zone
    zone_count: int | None = None
    zone_names: str | None = None

    # Nisi reference
    nisi_all_risk: float | None = None


class SeasonalRiskZone(BaseModel):
    """Seasonal collision risk for a single (h3_cell, season)."""

    h3_cell: int
    season: str
    cell_lat: float
    cell_lon: float
    risk_score: float
    risk_category: str
    scores: RiskScores
    flags: RiskFlags


class RiskZoneListResponse(BaseModel):
    """Paginated list of risk zone summaries."""

    total: int
    offset: int
    limit: int
    data: list[RiskZoneSummary]


class SeasonalRiskListResponse(BaseModel):
    """Paginated list of seasonal risk zones."""

    total: int
    offset: int
    limit: int
    data: list[SeasonalRiskZone]


class RiskStatsResponse(BaseModel):
    """Aggregate statistics for a bounding box query."""

    total_cells: int
    avg_risk_score: float
    max_risk_score: float
    min_risk_score: float
    category_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Count of cells per risk category",
    )


class NearestRiskResponse(BaseModel):
    """Nearest risk cell result with match metadata."""

    is_exact_match: bool
    query_lat: float
    query_lon: float
    distance_km: float
    cell: RiskZoneDetail
