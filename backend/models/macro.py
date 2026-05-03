"""Pydantic models for macro overview endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MacroCell(BaseModel):
    """One coarse H3 res-4 cell with aggregated scores."""

    h3_cell: int
    cell_lat: float
    cell_lon: float
    season: str = "annual"
    scenario: str | None = None
    decade: str | None = None

    # Composite risk
    risk_score: float | None = None
    ml_risk_score: float | None = None
    traffic_score: float | None = None
    avg_monthly_vessels: float | None = None
    avg_speed_lethality: float | None = None
    avg_high_speed_fraction: float | None = None
    avg_draft_risk_fraction: float | None = None
    night_traffic_ratio: float | None = None
    avg_commercial_vessels: float | None = None
    cetacean_score: float | None = None
    strike_score: float | None = None
    habitat_score: float | None = None
    proximity_score: float | None = None
    protection_gap: float | None = None
    reference_risk: float | None = None

    # Raw counts
    total_sightings: int | None = None
    baleen_sightings: int | None = None
    total_strikes: int | None = None

    # ISDM whale predictions
    any_whale_prob: float | None = None
    isdm_blue_whale: float | None = None
    isdm_fin_whale: float | None = None
    isdm_humpback_whale: float | None = None
    isdm_sperm_whale: float | None = None

    # SDM (OBIS-trained) whale predictions
    sdm_any_whale: float | None = None
    sdm_blue_whale: float | None = None
    sdm_fin_whale: float | None = None
    sdm_humpback_whale: float | None = None
    sdm_sperm_whale: float | None = None
    sdm_right_whale: float | None = None
    sdm_minke_whale: float | None = None

    # Ocean covariates
    sst: float | None = None
    sst_sd: float | None = None
    mld: float | None = None
    sla: float | None = None
    pp_upper_200m: float | None = None

    # Bathymetry
    depth_m_mean: float | None = None
    shelf_fraction: float | None = None

    # Aggregation metadata
    child_cell_count: int | None = None


class MacroOverviewResponse(BaseModel):
    """Response for the macro overview endpoint."""

    total: int
    season: str
    scenario: str | None = None
    decade: str | None = None
    data: list[MacroCell]


class ContourProperties(BaseModel):
    """Properties of a bathymetry contour feature."""

    depth_m: int
    label: str
    style: str = Field(description="'major' or 'minor'")
