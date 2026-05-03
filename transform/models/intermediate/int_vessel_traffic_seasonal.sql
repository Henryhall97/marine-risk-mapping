-- Intermediate model: vessel traffic per hex cell per season
-- Aggregates monthly AIS traffic data into seasonal summaries.

{{ config(
    indexes=[
        {'columns': ['h3_cell', 'season']},
    ]
) }}

--
-- Same metrics as int_vessel_traffic but at (h3_cell, season) grain
-- instead of (h3_cell, month). Uses the season_from_month macro.
--
-- Grain: one row per (h3_cell, season).

with monthly as (

    select
        *,
        {{ season_from_month("extract(month from month)::int") }} as season
    from {{ ref('int_vessel_traffic') }}

)

select
    h3_cell,
    season,

    -- ── Activity breadth ──────────────────────────────
    count(distinct month)                     as months_active,
    sum(ping_count)                           as total_pings,

    -- ── Vessel volume ─────────────────────────────────
    avg(unique_vessels)                       as avg_monthly_vessels,
    max(unique_vessels)                       as peak_monthly_vessels,

    -- ── Speed risk ────────────────────────────────────
    avg(vw_avg_speed_knots)                   as avg_speed_knots,
    max(max_speed_knots)                      as peak_speed_knots,
    avg(high_speed_vessel_count)              as avg_high_speed_vessels,
    sum(high_speed_pings)                     as total_high_speed_pings,

    -- ── Size risk ─────────────────────────────────────
    avg(large_vessel_count)                   as avg_large_vessels,
    avg(vw_avg_length_m)                      as avg_vessel_length_m,
    avg(deep_draft_count)                     as avg_deep_draft_vessels,

    -- ── Course diversity ──────────────────────────────
    avg(cross_vessel_circ_cog_stddev)         as avg_cog_diversity,

    -- ── Night risk ────────────────────────────────────
    avg(night_unique_vessels)                 as avg_night_vessels,
    avg(night_high_speed_vessel_count)        as avg_night_high_speed,
    avg(
        night_unique_vessels::float
        / nullif(
            coalesce(day_unique_vessels, 0)
            + coalesce(night_unique_vessels, 0), 0
        )
    )                                         as night_traffic_ratio,

    -- ── Vessel type mix ───────────────────────────────
    avg(cargo_vessels + tanker_vessels)        as avg_commercial_vessels,
    avg(fishing_vessels)                       as avg_fishing_vessels,
    avg(passenger_vessels)                     as avg_passenger_vessels,

    -- ── Literature-based risk metrics ─────────────────
    -- V&T (2007) speed-lethality (monthly index → seasonal avg)
    avg(speed_lethality_index)                as avg_speed_lethality,
    -- Fraction of vessels at lethal speeds
    avg(high_speed_fraction)                  as avg_high_speed_fraction,
    -- Fraction of vessels with deep draft (>8m)
    avg(draft_risk_fraction)                  as avg_draft_risk_fraction,
    -- Imputed cell-average draft (OLS from length where missing)
    avg(draft_imputed_m)                      as avg_draft_imputed_m

from monthly
where season is not null
group by h3_cell, season
