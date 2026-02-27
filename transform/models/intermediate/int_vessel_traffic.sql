-- Intermediate model: vessel traffic per hex cell per month
-- Selects key traffic metrics from the AIS H3 summary for
-- the downstream risk model.
--
-- Uses vessel-weighted (vw_) metrics where available — these
-- correct for AIS ping-rate bias where Class A ships broadcast
-- 15x more than Class B.
--
-- Grain: one row per (h3_cell, month).

select
    h3_cell,
    month,
    cell_lat,
    cell_lon,

    -- ── Traffic volume ───────────────────────────────
    ping_count,
    unique_vessels,

    -- ── Speed (vessel-weighted = debiased) ───────────
    vw_avg_speed_knots,
    vw_median_speed_knots,
    max_speed_knots,
    high_speed_pings,
    high_speed_vessel_count,

    -- ── Vessel size ──────────────────────────────────
    vw_avg_length_m,
    max_length_m,
    p95_length_m,
    large_vessel_count,
    length_report_count,

    vw_avg_width_m,
    max_width_m,
    wide_vessel_count,

    vw_avg_draft_m,
    max_draft_m,
    p95_draft_m,
    deep_draft_count,
    draft_report_count,

    -- ── Course diversity (circular statistics) ───────
    -- avg_circ_cog_stddev:  within-vessel maneuvering
    -- cross_vessel_*:       heading diversity across vessels
    avg_circ_cog_stddev,
    cross_vessel_circ_cog_stddev,
    cog_vessel_count,

    -- ── Day / Night ──────────────────────────────────
    day_unique_vessels,
    night_unique_vessels,
    vw_day_avg_speed_knots,
    vw_night_avg_speed_knots,
    day_high_speed_vessel_count,
    night_high_speed_vessel_count,

    -- ── Vessel type mix (vessel-weighted) ────────────
    fishing_vessels,
    tug_vessels,
    passenger_vessels,
    cargo_vessels,
    tanker_vessels,
    pleasure_vessels,
    military_vessels,

    -- ── Navigational status ──────────────────────────
    restricted_vessel_count

from {{ source('marine_risk', 'ais_h3_summary') }}
