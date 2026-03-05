"""Service layer for macro overview queries."""

from __future__ import annotations

import logging

from backend.services.database import fetch_all, fetch_scalar

logger = logging.getLogger(__name__)

VALID_SEASONS = {"annual", "winter", "spring", "summer", "fall"}


def get_macro_overview(season: str = "annual") -> list[dict]:
    """Return all coarse H3 res-4 cells for a given season."""
    if season not in VALID_SEASONS:
        season = "annual"

    sql = """
        SELECT h3_cell, cell_lat, cell_lon, season,
               risk_score, ml_risk_score, traffic_score,
               avg_monthly_vessels, avg_speed_lethality,
               avg_high_speed_fraction, avg_draft_risk_fraction,
               night_traffic_ratio, avg_commercial_vessels,
               cetacean_score,
               strike_score, habitat_score, proximity_score,
               protection_gap, reference_risk,
               total_sightings, baleen_sightings, total_strikes,
               any_whale_prob, isdm_blue_whale, isdm_fin_whale,
               isdm_humpback_whale, isdm_sperm_whale,
               sdm_any_whale, sdm_blue_whale, sdm_fin_whale,
               sdm_humpback_whale, sdm_sperm_whale,
               sst, pp_upper_200m, depth_m_mean, shelf_fraction,
               child_cell_count
        FROM macro_risk_overview
        WHERE season = %(season)s
        ORDER BY h3_cell
    """
    return fetch_all(sql, {"season": season})


def count_macro_overview(season: str = "annual") -> int:
    """Count cells for a given season."""
    if season not in VALID_SEASONS:
        season = "annual"

    sql = """
        SELECT count(*)
        FROM macro_risk_overview
        WHERE season = %(season)s
    """
    return fetch_scalar(sql, {"season": season}) or 0
