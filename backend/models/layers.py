"""Pydantic schemas for spatial layer overlay endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── Bathymetry ──────────────────────────────────────────────


class BathymetryCell(BaseModel):
    """Bathymetry data for a single H3 cell."""

    h3_cell: int
    cell_lat: float
    cell_lon: float
    depth_m: float | None = None
    min_depth_m: float | None = None
    max_depth_m: float | None = None
    depth_range_m: float | None = None
    depth_zone: str | None = None
    is_continental_shelf: bool | None = None
    is_shelf_edge: bool | None = None
    is_land: bool | None = None


class BathymetryListResponse(BaseModel):
    """Paginated bathymetry layer."""

    total: int
    offset: int
    limit: int
    data: list[BathymetryCell]


# ── Ocean covariates ────────────────────────────────────────


class OceanCovariateCell(BaseModel):
    """Ocean covariate data for a single H3 cell (optionally seasonal)."""

    h3_cell: int
    cell_lat: float
    cell_lon: float
    season: str | None = None
    sst: float | None = None
    sst_sd: float | None = None
    mld: float | None = None
    sla: float | None = None
    pp_upper_200m: float | None = None


class OceanCovariateListResponse(BaseModel):
    """Paginated ocean covariate layer."""

    total: int
    offset: int
    limit: int
    data: list[OceanCovariateCell]


# ── Whale predictions (ISDM) ───────────────────────────────


class WhalePredictionCell(BaseModel):
    """ISDM whale prediction for a single (h3_cell, season)."""

    h3_cell: int
    cell_lat: float
    cell_lon: float
    season: str | None = None
    isdm_blue_whale: float | None = None
    isdm_fin_whale: float | None = None
    isdm_humpback_whale: float | None = None
    isdm_sperm_whale: float | None = None
    max_whale_prob: float | None = None
    mean_whale_prob: float | None = None
    any_whale_prob: float | None = None


class WhalePredictionListResponse(BaseModel):
    """Paginated whale prediction layer."""

    total: int
    offset: int
    limit: int
    data: list[WhalePredictionCell]


# ── SDM whale predictions (OBIS-trained) ───────────────────


class SdmPredictionCell(BaseModel):
    """SDM (OBIS) whale prediction for a single (h3_cell, season)."""

    h3_cell: int
    cell_lat: float
    cell_lon: float
    season: str | None = None
    sdm_any_whale: float | None = None
    sdm_blue_whale: float | None = None
    sdm_fin_whale: float | None = None
    sdm_humpback_whale: float | None = None
    sdm_sperm_whale: float | None = None
    max_whale_prob: float | None = None
    mean_whale_prob: float | None = None
    any_whale_prob_joint: float | None = None


class SdmPredictionListResponse(BaseModel):
    """Paginated SDM prediction layer."""

    total: int
    offset: int
    limit: int
    data: list[SdmPredictionCell]


# ── MPA coverage ────────────────────────────────────────────


class MPACell(BaseModel):
    """MPA coverage for a single H3 cell."""

    h3_cell: int
    cell_lat: float
    cell_lon: float
    mpa_count: int | None = None
    mpa_names: str | None = None
    protection_level: str | None = None
    has_no_take_zone: bool | None = None


class MPAListResponse(BaseModel):
    """Paginated MPA layer."""

    total: int
    offset: int
    limit: int
    data: list[MPACell]


# ── Speed zones ─────────────────────────────────────────────


class SpeedZoneCell(BaseModel):
    """Speed zone coverage for a single H3 cell."""

    h3_cell: int
    cell_lat: float
    cell_lon: float
    season: str | None = None
    zone_count: int | None = None
    zone_names: str | None = None
    current_sma_count: int | None = None
    proposed_zone_count: int | None = None
    max_season_days: int | None = None
    season_labels: str | None = None


class SpeedZoneListResponse(BaseModel):
    """Paginated speed zone layer."""

    total: int
    offset: int
    limit: int
    data: list[SpeedZoneCell]


# ── Proximity ───────────────────────────────────────────────


class ProximityCell(BaseModel):
    """Proximity distances and decay scores for a single H3 cell."""

    h3_cell: int
    cell_lat: float
    cell_lon: float
    dist_to_nearest_whale_km: float | None = None
    dist_to_nearest_ship_km: float | None = None
    dist_to_nearest_strike_km: float | None = None
    dist_to_nearest_protection_km: float | None = None
    whale_proximity_score: float | None = None
    ship_proximity_score: float | None = None
    strike_proximity_score: float | None = None
    protection_proximity_score: float | None = None


class ProximityListResponse(BaseModel):
    """Paginated proximity layer."""

    total: int
    offset: int
    limit: int
    data: list[ProximityCell]


# ── Nisi reference risk ─────────────────────────────────────


class NisiRiskCell(BaseModel):
    """Nisi et al. reference risk for a single H3 cell."""

    h3_cell: int
    cell_lat: float
    cell_lon: float
    nisi_all_risk: float | None = None
    nisi_shipping_index: float | None = None
    nisi_whale_space_use: float | None = None
    nisi_blue_risk: float | None = None
    nisi_fin_risk: float | None = None
    nisi_humpback_risk: float | None = None
    nisi_sperm_risk: float | None = None
    nisi_has_management: bool | None = None
    nisi_has_mandatory_mgmt: bool | None = None
    nisi_hotspot_overlap: bool | None = None


class NisiRiskListResponse(BaseModel):
    """Paginated Nisi reference risk layer."""

    total: int
    offset: int
    limit: int
    data: list[NisiRiskCell]


# ── Cetacean density ────────────────────────────────────────


class CetaceanDensityCell(BaseModel):
    """Cetacean sighting density for a single H3 cell."""

    h3_cell: int
    cell_lat: float
    cell_lon: float
    season: str | None = None
    total_sightings: int | None = None
    unique_species: int | None = None
    baleen_sightings: int | None = None
    recent_sightings: int | None = None
    right_whale_sightings: int | None = None
    humpback_sightings: int | None = None
    fin_whale_sightings: int | None = None
    blue_whale_sightings: int | None = None
    sperm_whale_sightings: int | None = None
    minke_whale_sightings: int | None = None


class CetaceanDensityListResponse(BaseModel):
    """Paginated cetacean density layer."""

    total: int
    offset: int
    limit: int
    data: list[CetaceanDensityCell]


# ── Ship strike density ─────────────────────────────────────


class StrikeDensityCell(BaseModel):
    """Ship strike history for a single H3 cell."""

    h3_cell: int
    cell_lat: float
    cell_lon: float
    total_strikes: int | None = None
    fatal_strikes: int | None = None
    serious_injury_strikes: int | None = None
    baleen_strikes: int | None = None
    right_whale_strikes: int | None = None
    unique_species_groups: int | None = None
    species_list: str | None = None


class StrikeDensityListResponse(BaseModel):
    """Paginated strike density layer."""

    total: int
    offset: int
    limit: int
    data: list[StrikeDensityCell]


# ── ML risk ─────────────────────────────────────────────────


class MLRiskScores(BaseModel):
    """The 7 sub-scores in the ML-enhanced risk model."""

    whale_traffic_interaction: float | None = None
    traffic_score: float | None = None
    whale_ml_exposure: float | None = None
    proximity_score: float | None = None
    strike_score: float | None = None
    protection_gap: float | None = None
    reference_risk_score: float | None = None


class MLRiskZoneSummary(BaseModel):
    """Compact ML risk for map tiles."""

    h3_cell: int
    season: str | None = None
    cell_lat: float
    cell_lon: float
    risk_score: float
    risk_category: str


class MLRiskZoneDetail(MLRiskZoneSummary):
    """Full ML risk detail for a single H3 cell."""

    scores: MLRiskScores
    any_whale_prob: float | None = None
    max_whale_prob: float | None = None
    mean_whale_prob: float | None = None
    isdm_blue_whale: float | None = None
    isdm_fin_whale: float | None = None
    isdm_humpback_whale: float | None = None
    isdm_sperm_whale: float | None = None


class MLRiskListResponse(BaseModel):
    """Paginated list of ML risk zones."""

    total: int
    offset: int
    limit: int
    data: list[MLRiskZoneSummary]


class MLRiskStatsResponse(BaseModel):
    """Aggregate ML risk statistics for a bounding box."""

    total_cells: int
    avg_risk_score: float
    max_risk_score: float
    min_risk_score: float
    category_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Count of cells per risk category",
    )


# ── Risk breakdown ──────────────────────────────────────────


class TrafficBreakdown(BaseModel):
    """Detailed traffic sub-score components."""

    traffic_score: float | None = None
    pctl_vessels: float | None = None
    pctl_speed_lethality: float | None = None
    pctl_large_vessels: float | None = None
    pctl_draft_risk: float | None = None
    pctl_high_speed_fraction: float | None = None
    pctl_draft_risk_fraction: float | None = None
    pctl_commercial: float | None = None
    pctl_night_traffic: float | None = None


class RiskBreakdown(BaseModel):
    """Full risk breakdown for a single H3 cell — explains why."""

    h3_cell: int
    cell_lat: float
    cell_lon: float
    risk_score: float
    risk_category: str
    traffic: TrafficBreakdown | None = None
    cetacean_score: float | None = None
    total_sightings: int | None = None
    unique_species: int | None = None
    proximity_score: float | None = None
    dist_to_nearest_whale_km: float | None = None
    dist_to_nearest_ship_km: float | None = None
    strike_score: float | None = None
    total_strikes: int | None = None
    habitat_score: float | None = None
    depth_m: float | None = None
    depth_zone: str | None = None
    sst: float | None = None
    pp_upper_200m: float | None = None
    protection_gap: float | None = None
    mpa_count: int | None = None
    in_speed_zone: bool | None = None
    reference_risk_score: float | None = None
    nisi_all_risk: float | None = None


# ── Risk compare ────────────────────────────────────────────


class RiskCompare(BaseModel):
    """Side-by-side standard vs ML risk for a cell."""

    h3_cell: int
    cell_lat: float
    cell_lon: float
    standard_risk_score: float | None = None
    standard_risk_category: str | None = None
    ml_risk_score: float | None = None
    ml_risk_category: str | None = None
    score_difference: float | None = None


class RiskCompareListResponse(BaseModel):
    """Paginated risk comparison list."""

    total: int
    offset: int
    limit: int
    data: list[RiskCompare]


# ── Seasonal species ────────────────────────────────────────


class SeasonalSpeciesCell(BaseModel):
    """Seasonal species distribution for a single (h3_cell, season)."""

    h3_cell: int
    cell_lat: float
    cell_lon: float
    season: str
    total_sightings: int | None = None
    unique_species: int | None = None
    baleen_sightings: int | None = None
    recent_sightings: int | None = None
    right_whale_sightings: int | None = None
    humpback_sightings: int | None = None
    fin_whale_sightings: int | None = None
    blue_whale_sightings: int | None = None
    sperm_whale_sightings: int | None = None
    minke_whale_sightings: int | None = None


class SeasonalSpeciesListResponse(BaseModel):
    """Paginated seasonal species list."""

    total: int
    offset: int
    limit: int
    data: list[SeasonalSpeciesCell]


# ── Seasonal traffic ────────────────────────────────────────


class SeasonalTrafficCell(BaseModel):
    """Seasonal traffic aggregate for a single (h3_cell, season)."""

    h3_cell: int
    cell_lat: float
    cell_lon: float
    season: str
    total_months: int | None = None
    total_pings: int | None = None
    avg_monthly_vessels: float | None = None
    avg_speed_knots: float | None = None
    avg_high_speed_fraction: float | None = None
    avg_draft_risk_fraction: float | None = None
    avg_large_vessels: float | None = None
    avg_commercial_vessels: float | None = None
    avg_fishing_vessels: float | None = None
    avg_night_fraction: float | None = None


class SeasonalTrafficListResponse(BaseModel):
    """Paginated seasonal traffic list."""

    total: int
    offset: int
    limit: int
    data: list[SeasonalTrafficCell]


# ── Traffic density (detail hex) ────────────────────────────


class TrafficDensityCell(BaseModel):
    """Vessel traffic metrics for a single H3 cell.

    Exposes the 8 key danger indicators from the composite traffic
    sub-score: speed lethality (V&T 2007), high-speed fraction,
    vessel volume, large vessels, draft risk, commercial traffic,
    and night operations.
    """

    h3_cell: int
    cell_lat: float
    cell_lon: float
    season: str | None = None
    # Volume
    avg_monthly_vessels: float | None = Field(
        None,
        description="Mean unique vessels per month",
    )
    total_pings: int | None = Field(
        None,
        description="Total AIS pings in period",
    )
    # Speed lethality — the #1 danger metric
    avg_speed_lethality: float | None = Field(
        None,
        description="V&T 2007 logistic lethality index (0–1)",
    )
    avg_speed_knots: float | None = None
    peak_speed_knots: float | None = None
    avg_high_speed_fraction: float | None = Field(
        None,
        description="Fraction of vessels at ≥10 kn lethal speed",
    )
    # Vessel size & draft
    avg_vessel_length_m: float | None = None
    avg_deep_draft_vessels: float | None = Field(
        None,
        description="Avg vessels with >8m draft per month",
    )
    avg_draft_risk_fraction: float | None = Field(
        None,
        description="Fraction with deep draft (>8m)",
    )
    avg_large_vessels: float | None = None
    # Vessel composition
    avg_commercial_vessels: float | None = Field(
        None,
        description="Avg cargo + tanker per month",
    )
    avg_fishing_vessels: float | None = None
    avg_passenger_vessels: float | None = None
    # Night operations
    avg_night_vessels: float | None = None
    avg_night_high_speed: float | None = Field(
        None,
        description="Avg night vessels at ≥10 kn",
    )
    night_traffic_ratio: float | None = Field(
        None,
        description="Night/(day+night) vessel ratio",
    )
    # Course diversity (erratic routing)
    avg_cog_diversity: float | None = Field(
        None,
        description="Cross-vessel COG circular std dev",
    )
    # Imputed draft
    avg_draft_imputed_m: float | None = None
    months_active: int | None = None


class TrafficDensityListResponse(BaseModel):
    """Paginated traffic density layer."""

    total: int
    offset: int
    limit: int
    data: list[TrafficDensityCell]
