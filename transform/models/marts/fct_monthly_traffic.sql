-- Mart model: monthly vessel traffic enriched with cell context
--
-- Joins monthly traffic with static cell-level features from
-- the intermediate layer. Powers temporal drill-down in the
-- API — e.g. "show me vessel traffic over time for this cell".
--
-- Keeps a focused subset of traffic columns (the most useful
-- for charts and filters) plus compact cell context so the API
-- doesn't need to join multiple tables.
--
-- Land cells are excluded.
--
-- Grain: one row per (h3_cell, month).

{{ config(
    indexes=[
        {'columns': ['h3_cell']},
        {'columns': ['month']},
        {'columns': ['h3_cell', 'month'], 'unique': true},
    ]
) }}

select
    t.h3_cell,
    t.month,
    t.cell_lat,
    t.cell_lon,

    -- ── Core traffic metrics (for time series) ──────
    t.unique_vessels,
    t.ping_count,
    t.vw_avg_speed_knots,
    t.vw_median_speed_knots,
    t.max_speed_knots,
    t.high_speed_vessel_count,
    t.large_vessel_count,

    -- ── Day / Night split ───────────────────────────
    t.day_unique_vessels,
    t.night_unique_vessels,

    -- ── Vessel type breakdown ───────────────────────
    t.cargo_vessels,
    t.tanker_vessels,
    t.fishing_vessels,
    t.passenger_vessels,
    t.pleasure_vessels,

    -- ── Cell-level context (static, denormalised) ───
    coalesce(b.depth_zone, 'unknown')           as depth_zone,
    coalesce(b.is_continental_shelf, false)      as is_continental_shelf,
    coalesce(b.depth_m, 0)                       as depth_m,
    coalesce(c.total_sightings, 0)              as total_sightings,
    coalesce(c.baleen_whale_sightings, 0)       as baleen_whale_sightings,
    m.h3_cell is not null                       as in_mpa

from {{ ref('int_vessel_traffic') }} t
left join {{ ref('int_bathymetry') }} b
    on t.h3_cell = b.h3_cell
left join {{ ref('int_cetacean_density') }} c
    on t.h3_cell = c.h3_cell
left join {{ ref('int_mpa_coverage') }} m
    on t.h3_cell = m.h3_cell

-- Exclude land cells
where coalesce(b.is_land, false) = false
