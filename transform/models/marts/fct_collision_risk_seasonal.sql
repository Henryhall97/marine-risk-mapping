-- Mart model: seasonal whale–vessel collision risk per H3 cell
--
-- Same 7-sub-score architecture as fct_collision_risk but at
-- (h3_cell, season) grain. Seasonal inputs where available:
--   - Traffic: seasonal aggregate from int_vessel_traffic_seasonal
--   - Cetacean: seasonal sightings from int_cetacean_density_seasonal
--   - Speed zones: only zones active in that season
-- Static inputs reused across all seasons:
--   - Bathymetry, proximity, strike history, MPA, Nisi, ocean covariates
--
-- Percentile ranking is done WITHIN each season so sub-scores
-- are comparable across seasons (each season has its own 0–1 scale).
--
-- Grain: one row per (h3_cell, season).

{{ config(
    indexes=[
        {'columns': ['h3_cell', 'season']},
        {'columns': ['risk_score']},
        {'columns': ['geom'], 'type': 'gist'},
    ]
) }}

with seasons as (

    select unnest(array['winter', 'spring', 'summer', 'fall']) as season

),

-- Expand hex grid × 4 seasons as the spine
grid_seasons as (

    select
        g.h3_cell,
        g.cell_lat,
        g.cell_lon,
        g.geom,
        s.season
    from {{ ref('int_hex_grid') }} g
    cross join seasons s

),

features as (

    select
        gs.h3_cell,
        gs.cell_lat,
        gs.cell_lon,
        gs.geom,
        gs.season,

        -- ── Seasonal traffic ───────────────────────────
        t.months_active,
        t.total_pings,
        t.avg_monthly_vessels,
        t.peak_monthly_vessels,
        t.avg_speed_knots,
        t.peak_speed_knots,
        t.avg_high_speed_vessels,
        t.total_high_speed_pings,
        t.avg_large_vessels,
        t.avg_vessel_length_m,
        t.avg_deep_draft_vessels,
        t.avg_speed_lethality,
        t.avg_high_speed_fraction,
        t.avg_draft_risk_fraction,
        t.avg_draft_imputed_m,
        t.avg_cog_diversity,
        t.avg_night_vessels,
        t.avg_night_high_speed,
        t.night_traffic_ratio,
        t.avg_commercial_vessels,
        t.avg_fishing_vessels,
        t.avg_passenger_vessels,

        -- ── Seasonal cetacean ──────────────────────────
        c.total_sightings,
        c.unique_species,
        c.species_level_sightings,
        c.recent_sightings,
        c.baleen_whale_sightings,

        -- ── Static: bathymetry ─────────────────────────
        b.depth_m,
        b.depth_range_m,
        b.is_continental_shelf,
        b.is_shelf_edge,
        b.depth_zone,

        -- ── Static: MPA ────────────────────────────────
        m.mpa_count,
        m.has_strict_protection,
        m.has_no_take_zone,

        -- ── Static: proximity ──────────────────────────
        p.dist_to_nearest_whale_km,
        p.dist_to_nearest_ship_km,
        p.dist_to_nearest_strike_km,
        p.dist_to_nearest_protection_km,
        p.whale_proximity_score,
        p.ship_proximity_score,
        p.strike_proximity_score,
        p.protection_proximity_score,

        -- ── Static: strike history ─────────────────────
        ss.total_strikes,
        ss.fatal_strikes,
        ss.serious_injury_strikes,
        ss.baleen_strikes,
        ss.right_whale_strikes,

        -- ── Seasonal: speed zone ───────────────────────
        coalesce(sz.in_speed_zone, false)    as in_speed_zone,
        coalesce(sz.in_current_sma, false)   as in_current_sma,
        coalesce(sz.in_proposed_zone, false) as in_proposed_zone,
        sz.zone_count,
        sz.max_season_days,

        -- ── Static: Nisi reference ─────────────────────
        nr.nisi_all_risk,
        nr.nisi_shipping_index,
        nr.nisi_whale_space_use,
        nr.nisi_hotspot_overlap,

        -- ── Seasonal: ocean covariates ─────────────────
        oc.sst,
        oc.sst_sd,
        oc.mld,
        oc.sla,
        oc.pp_upper_200m,

        -- Convenience booleans
        t.h3_cell is not null      as has_traffic,
        c.h3_cell is not null      as has_whale_sightings,
        m.h3_cell is not null      as in_mpa,
        ss.h3_cell is not null     as has_strike_history,
        nr.h3_cell is not null     as has_nisi_reference

    from grid_seasons gs
    left join {{ ref('int_vessel_traffic_seasonal') }} t
        on gs.h3_cell = t.h3_cell and gs.season = t.season
    left join {{ ref('int_cetacean_density_seasonal') }} c
        on gs.h3_cell = c.h3_cell and gs.season = c.season
    left join {{ ref('int_bathymetry') }} b
        on gs.h3_cell = b.h3_cell
    left join {{ ref('int_mpa_coverage') }} m
        on gs.h3_cell = m.h3_cell
    left join {{ ref('int_proximity') }} p
        on gs.h3_cell = p.h3_cell
    left join {{ ref('int_ship_strike_density') }} ss
        on gs.h3_cell = ss.h3_cell
    left join {{ ref('int_speed_zone_coverage_seasonal') }} sz
        on gs.h3_cell = sz.h3_cell and gs.season = sz.season
    left join {{ ref('int_nisi_reference_risk') }} nr
        on gs.h3_cell = nr.h3_cell
    left join {{ ref('int_ocean_covariates_seasonal') }} oc
        on gs.h3_cell = oc.h3_cell and gs.season = oc.season

    -- Exclude land cells
    where coalesce(b.is_land, false) = false

),

ranked as (

    -- Percentile-rank WITHIN each season
    select
        *,

        -- Traffic percentiles
        percent_rank() over (partition by season order by coalesce(avg_monthly_vessels, 0))
            as pctl_vessels,
        percent_rank() over (partition by season order by coalesce(avg_speed_lethality, 0))
            as pctl_speed_lethality,
        percent_rank() over (partition by season order by coalesce(avg_large_vessels, 0))
            as pctl_large_vessels,
        percent_rank() over (partition by season order by coalesce(avg_draft_imputed_m, 0))
            as pctl_draft_risk,
        percent_rank() over (partition by season order by coalesce(avg_high_speed_fraction, 0))
            as pctl_high_speed_fraction,
        percent_rank() over (partition by season order by coalesce(avg_draft_risk_fraction, 0))
            as pctl_draft_risk_fraction,
        percent_rank() over (partition by season order by coalesce(avg_commercial_vessels, 0))
            as pctl_commercial,
        percent_rank() over (partition by season order by coalesce(avg_night_vessels, 0))
            as pctl_night_traffic,

        -- Cetacean percentiles
        percent_rank() over (partition by season order by coalesce(total_sightings, 0))
            as pctl_sightings,
        percent_rank() over (partition by season order by coalesce(baleen_whale_sightings, 0))
            as pctl_baleen,
        percent_rank() over (partition by season order by coalesce(recent_sightings, 0))
            as pctl_recent_sightings,

        -- Strike percentiles (same across seasons — static data)
        percent_rank() over (partition by season order by coalesce(total_strikes, 0))
            as pctl_strikes,
        percent_rank() over (partition by season order by coalesce(fatal_strikes, 0))
            as pctl_fatal_strikes,
        percent_rank() over (partition by season order by coalesce(baleen_strikes, 0))
            as pctl_baleen_strikes,

        -- Nisi reference percentile
        percent_rank() over (partition by season order by coalesce(nisi_all_risk, 0))
            as pctl_nisi_risk

    from features

),

scored as (

    select
        *,

        -- V&T speed-lethality + fractions for improved traffic threat
        (
            0.20 * pctl_speed_lethality
          + 0.10 * pctl_high_speed_fraction
          + 0.20 * pctl_vessels
          + 0.10 * pctl_large_vessels
          + 0.10 * pctl_draft_risk
          + 0.05 * pctl_draft_risk_fraction
          + 0.10 * pctl_commercial
          + 0.15 * pctl_night_traffic
        ) as traffic_score,

        (
            0.35 * pctl_sightings
          + 0.35 * pctl_baleen
          + 0.30 * pctl_recent_sightings
        ) as cetacean_score,

        (
            0.40 * pctl_strikes
          + 0.35 * pctl_fatal_strikes
          + 0.25 * pctl_baleen_strikes
        ) as strike_score,

        (
            0.50 * coalesce(is_continental_shelf::int, 0)
          + 0.30 * coalesce(is_shelf_edge::int, 0)
          + 0.20 * case coalesce(depth_zone, 'unknown')
                       when 'shelf'   then 1.0
                       when 'slope'   then 0.5
                       when 'abyssal' then 0.1
                       else 0.0
                   end
        ) as habitat_score,

        case
            when coalesce(in_current_sma, false) and coalesce(has_no_take_zone, false)
                then 0.1
            when coalesce(in_current_sma, false)
                then 0.2
            when coalesce(in_proposed_zone, false) and in_mpa
                then 0.3
            when coalesce(has_no_take_zone, false)
                then 0.3
            when coalesce(in_proposed_zone, false)
                then 0.4
            when coalesce(has_strict_protection, false)
                then 0.5
            when in_mpa
                then 0.7
            else 1.0
        end as protection_gap,

        (
            0.45 * sqrt(
                coalesce(whale_proximity_score, 0)
              * coalesce(ship_proximity_score, 0)
            )
          + 0.30 * coalesce(strike_proximity_score, 0)
          + 0.25 * (1.0 - coalesce(protection_proximity_score, 0))
        ) as proximity_score,

        pctl_nisi_risk as reference_risk_score

    from ranked

)

select
    h3_cell,
    season,
    cell_lat,
    cell_lon,
    geom,

    -- ── Composite risk score ────────────────────────
    round((
        0.25 * traffic_score
      + 0.25 * cetacean_score
      + 0.15 * proximity_score
      + 0.10 * strike_score
      + 0.10 * habitat_score
      + 0.10 * protection_gap
      + 0.05 * reference_risk_score
    )::numeric, 4) as risk_score,

    -- ── Risk category ───────────────────────────────
    case
        when (
            0.25 * traffic_score
          + 0.25 * cetacean_score
          + 0.15 * proximity_score
          + 0.10 * strike_score
          + 0.10 * habitat_score
          + 0.10 * protection_gap
          + 0.05 * reference_risk_score
        ) >= 0.7  then 'critical'
        when (
            0.25 * traffic_score
          + 0.25 * cetacean_score
          + 0.15 * proximity_score
          + 0.10 * strike_score
          + 0.10 * habitat_score
          + 0.10 * protection_gap
          + 0.05 * reference_risk_score
        ) >= 0.5  then 'high'
        when (
            0.25 * traffic_score
          + 0.25 * cetacean_score
          + 0.15 * proximity_score
          + 0.10 * strike_score
          + 0.10 * habitat_score
          + 0.10 * protection_gap
          + 0.05 * reference_risk_score
        ) >= 0.35 then 'medium'
        when (
            0.25 * traffic_score
          + 0.25 * cetacean_score
          + 0.15 * proximity_score
          + 0.10 * strike_score
          + 0.10 * habitat_score
          + 0.10 * protection_gap
          + 0.05 * reference_risk_score
        ) >= 0.2  then 'low'
        else 'minimal'
    end as risk_category,

    -- ── Sub-scores ──────────────────────────────────
    round(traffic_score::numeric, 4)         as traffic_score,
    round(cetacean_score::numeric, 4)        as cetacean_score,
    round(proximity_score::numeric, 4)       as proximity_score,
    round(strike_score::numeric, 4)          as strike_score,
    round(habitat_score::numeric, 4)         as habitat_score,
    round(protection_gap::numeric, 4)        as protection_gap,
    round(reference_risk_score::numeric, 4)  as reference_risk_score,

    -- ── Feature flags ───────────────────────────────
    has_traffic,
    has_whale_sightings,
    in_mpa,
    has_strike_history,
    in_speed_zone,
    in_current_sma,
    in_proposed_zone,
    has_nisi_reference

from scored
