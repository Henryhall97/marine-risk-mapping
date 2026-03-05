-- Mart model: strike risk prediction training set
--
-- One row per H3 cell with the historical strike count as
-- the target variable, plus all spatial, environmental, and
-- traffic features needed to train a strike-risk model.
--
-- Target variable:
--   has_strike (1/0) — binary classification target
--   total_strikes    — count regression target
--
-- This table is suitable for:
--   - Binary classification (has_strike): random forest, XGBoost
--   - Count regression (total_strikes): Poisson, negative binomial
--   - Zero-inflated models (>99% of cells have no strikes)
--
-- Feature groups mirror fct_collision_risk but are un-scored
-- (raw features) for ML to learn its own weights.
--
-- Grain: one row per h3_cell.

{{ config(
    indexes=[
        {'columns': ['h3_cell']},
        {'columns': ['geom'], 'type': 'gist'},
    ]
) }}

with traffic_agg as (

    select
        h3_cell,
        count(distinct month)                     as months_active,
        sum(ping_count)                           as total_pings,
        avg(unique_vessels)                       as avg_monthly_vessels,
        max(unique_vessels)                       as peak_monthly_vessels,
        avg(vw_avg_speed_knots)                   as avg_speed_knots,
        max(max_speed_knots)                      as peak_speed_knots,
        avg(high_speed_vessel_count)              as avg_high_speed_vessels,
        avg(large_vessel_count)                   as avg_large_vessels,
        avg(vw_avg_length_m)                      as avg_vessel_length_m,
        avg(deep_draft_count)                     as avg_deep_draft_vessels,
        avg(night_unique_vessels)                 as avg_night_vessels,
        avg(cargo_vessels + tanker_vessels)        as avg_commercial_vessels,
        avg(fishing_vessels)                       as avg_fishing_vessels,
        avg(passenger_vessels)                     as avg_passenger_vessels
    from {{ ref('int_vessel_traffic') }}
    group by h3_cell

),

base as (

    select
        g.h3_cell,
        g.cell_lat,
        g.cell_lon,
        g.geom,

        -- ══════ TARGET VARIABLES ══════════════════════
        case when ss.h3_cell is not null then 1 else 0 end
                                                  as has_strike,
        coalesce(ss.total_strikes, 0)             as total_strikes,
        coalesce(ss.fatal_strikes, 0)             as fatal_strikes,
        coalesce(ss.baleen_strikes, 0)            as baleen_strikes,
        coalesce(ss.right_whale_strikes, 0)       as right_whale_strikes,

        -- ══════ TRAFFIC FEATURES ═════════════════════
        t.months_active,
        t.total_pings,
        t.avg_monthly_vessels,
        t.peak_monthly_vessels,
        t.avg_speed_knots,
        t.peak_speed_knots,
        t.avg_high_speed_vessels,
        t.avg_large_vessels,
        t.avg_vessel_length_m,
        t.avg_deep_draft_vessels,
        t.avg_night_vessels,
        t.avg_commercial_vessels,
        t.avg_fishing_vessels,
        t.avg_passenger_vessels,

        -- ══════ CETACEAN FEATURES ════════════════════
        coalesce(c.total_sightings, 0)            as total_sightings,
        coalesce(c.unique_species, 0)              as unique_species,
        coalesce(c.baleen_whale_sightings, 0)      as baleen_whale_sightings,
        coalesce(c.recent_sightings, 0)            as recent_sightings,

        -- ══════ BATHYMETRY FEATURES ══════════════════
        b.depth_m,
        b.depth_range_m,
        coalesce(b.is_continental_shelf, false)    as is_continental_shelf,
        coalesce(b.is_shelf_edge, false)           as is_shelf_edge,
        b.depth_zone,

        -- ══════ OCEAN COVARIATES ═════════════════════
        oc.sst,
        oc.sst_sd,
        oc.mld,
        oc.sla,
        oc.pp_upper_200m,

        -- ══════ PROXIMITY FEATURES ═══════════════════
        p.dist_to_nearest_whale_km,
        p.dist_to_nearest_ship_km,
        p.whale_proximity_score,
        p.ship_proximity_score,
        p.dist_to_nearest_strike_km,
        p.strike_proximity_score,
        p.dist_to_nearest_protection_km,
        p.protection_proximity_score,

        -- ══════ SPEED ZONE FEATURES ══════════════════
        coalesce(sz.in_speed_zone, false)          as in_speed_zone,
        coalesce(sz.in_current_sma, false)         as in_current_sma,
        coalesce(sz.in_proposed_zone, false)        as in_proposed_zone,
        coalesce(sz.zone_count, 0)                 as zone_count,
        coalesce(sz.max_season_days, 0)            as max_season_days,

        -- ══════ MPA FEATURES ═════════════════════════
        coalesce(m.mpa_count, 0)                   as mpa_count,
        coalesce(m.has_strict_protection, false)   as has_strict_protection,
        coalesce(m.has_no_take_zone, false)        as has_no_take_zone,

        -- ══════ NISI REFERENCE ═══════════════════════
        nr.nisi_all_risk,
        nr.nisi_shipping_index,
        nr.nisi_whale_space_use,
        coalesce(nr.nisi_hotspot_overlap, 0)        as nisi_hotspot_overlap,

        -- ══════ EXCLUSION FLAGS ══════════════════════
        coalesce(b.is_ocean, false)                 as is_ocean

    from {{ ref('int_hex_grid') }} g
    left join {{ ref('int_ship_strike_density') }} ss
        on g.h3_cell = ss.h3_cell
    left join traffic_agg t
        on g.h3_cell = t.h3_cell
    left join {{ ref('int_cetacean_density') }} c
        on g.h3_cell = c.h3_cell
    left join {{ ref('int_bathymetry') }} b
        on g.h3_cell = b.h3_cell
    left join {{ ref('int_ocean_covariates') }} oc
        on g.h3_cell = oc.h3_cell
    left join {{ ref('int_proximity') }} p
        on g.h3_cell = p.h3_cell
    left join {{ ref('int_speed_zone_coverage') }} sz
        on g.h3_cell = sz.h3_cell
    left join {{ ref('int_mpa_coverage') }} m
        on g.h3_cell = m.h3_cell
    left join {{ ref('int_nisi_reference_risk') }} nr
        on g.h3_cell = nr.h3_cell

)

select * from base
where is_ocean
