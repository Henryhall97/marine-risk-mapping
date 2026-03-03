-- Mart model: whale–vessel collision risk per H3 cell
--
-- Joins all intermediate domains onto the hex grid and computes
-- a composite risk score on a 0–1 scale (higher = more dangerous).
--
-- Methodology:
--   1. Aggregate monthly vessel traffic to per-cell summaries
--   2. LEFT JOIN traffic, cetacean, bathymetry, MPA, proximity,
--      strike history, speed zones, Nisi reference, ocean covariates
--   3. Percentile-rank each risk-relevant feature (0–1)
--   4. Combine into seven sub-scores via weighted average
--   5. Final score = weighted sum of sub-scores
--
-- Sub-score weights (updated):
--   - Traffic threat      25%  (vessel density, speed, size)
--   - Cetacean exposure   25%  (sighting density, vulnerability)
--   - Proximity           15%  (co-location of whales and ships)
--   - Strike history      10%  (historical collision record)
--   - Habitat suitability 10%  (shelf, shelf edge, depth, ocean env)
--   - Protection gap      10%  (inverse of MPA/speed zone coverage)
--   - Reference risk       5%  (Nisi et al. 2024 benchmark)
--
-- Land cells are excluded. Cells with no data for a domain
-- get zero/null for those features and rank at the bottom.
--
-- Grain: one row per h3_cell (time-aggregated across months).

{{ config(
    indexes=[
        {'columns': ['h3_cell']},
        {'columns': ['risk_score']},
        {'columns': ['geom'], 'type': 'gist'},
    ]
) }}

with traffic_agg as (

    -- Collapse monthly vessel traffic to per-cell annual summaries
    select
        h3_cell,

        -- Activity breadth
        count(distinct month)                     as months_active,
        sum(ping_count)                           as total_pings,

        -- Vessel volume
        avg(unique_vessels)                       as avg_monthly_vessels,
        max(unique_vessels)                       as peak_monthly_vessels,

        -- Speed risk
        avg(vw_avg_speed_knots)                   as avg_speed_knots,
        max(max_speed_knots)                      as peak_speed_knots,
        avg(high_speed_vessel_count)              as avg_high_speed_vessels,
        sum(high_speed_pings)                     as total_high_speed_pings,

        -- Size risk
        avg(large_vessel_count)                   as avg_large_vessels,
        avg(vw_avg_length_m)                      as avg_vessel_length_m,
        avg(deep_draft_count)                     as avg_deep_draft_vessels,

        -- Literature-based risk metrics (V&T lethality, fractions)
        avg(speed_lethality_index)                as avg_speed_lethality,
        avg(high_speed_fraction)                  as avg_high_speed_fraction,
        avg(draft_risk_fraction)                  as avg_draft_risk_fraction,
        avg(draft_imputed_m)                      as avg_draft_imputed_m,

        -- Course diversity (maneuvering complexity)
        avg(cross_vessel_circ_cog_stddev)         as avg_cog_diversity,

        -- Night risk
        avg(night_unique_vessels)                 as avg_night_vessels,
        avg(night_high_speed_vessel_count)        as avg_night_high_speed,
        avg(
            night_unique_vessels::float
            / nullif(
                coalesce(day_unique_vessels, 0)
                + coalesce(night_unique_vessels, 0), 0
            )
        )                                         as night_traffic_ratio,

        -- Vessel type mix (most dangerous for strikes)
        avg(cargo_vessels + tanker_vessels)        as avg_commercial_vessels,
        avg(fishing_vessels)                       as avg_fishing_vessels,
        avg(passenger_vessels)                     as avg_passenger_vessels

    from {{ ref('int_vessel_traffic') }}
    group by h3_cell

),

features as (

    -- Join all domains onto the hex grid (spine)
    select
        g.h3_cell,
        g.cell_lat,
        g.cell_lon,
        g.geom,

        -- Traffic features (null = no vessel traffic in this cell)
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

        -- Cetacean features (null = no sightings in this cell)
        c.total_sightings,
        c.unique_species,
        c.species_level_sightings,
        c.recent_sightings,
        c.baleen_whale_sightings,
        c.earliest_year            as sighting_earliest_year,
        c.latest_year              as sighting_latest_year,

        -- Bathymetry features (null = outside GEBCO raster)
        b.depth_m,
        b.depth_range_m,
        b.is_continental_shelf,
        b.is_shelf_edge,
        b.depth_zone,

        -- MPA features (null = no MPA overlap)
        m.mpa_count,
        m.has_strict_protection,
        m.has_no_take_zone,

        -- Proximity features (distance to nearest whale / ship / strike / protection)
        p.dist_to_nearest_whale_km,
        p.dist_to_nearest_ship_km,
        p.dist_to_nearest_strike_km,
        p.dist_to_nearest_protection_km,
        p.whale_proximity_score,
        p.ship_proximity_score,
        p.strike_proximity_score,
        p.protection_proximity_score,

        -- Ship strike history features (null = no strikes in this cell)
        ss.total_strikes,
        ss.fatal_strikes,
        ss.serious_injury_strikes,
        ss.baleen_strikes,
        ss.right_whale_strikes,
        ss.unique_species_groups   as strike_species_groups,
        ss.species_list            as strike_species_list,

        -- Speed zone coverage (null = not in any speed zone)
        coalesce(sz.in_speed_zone, false)    as in_speed_zone,
        coalesce(sz.in_current_sma, false)   as in_current_sma,
        coalesce(sz.in_proposed_zone, false) as in_proposed_zone,
        sz.zone_count,
        sz.max_season_days,
        sz.zone_names,

        -- Nisi et al. (2024) reference risk (null = outside Nisi coverage)
        nr.nisi_all_risk,
        nr.nisi_shipping_index,
        nr.nisi_whale_space_use,
        nr.nisi_hotspot_overlap,
        nr.nisi_dist_km,

        -- Ocean environmental covariates (null = outside coverage)
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

    from {{ ref('int_hex_grid') }} g
    left join traffic_agg t
        on g.h3_cell = t.h3_cell
    left join {{ ref('int_cetacean_density') }} c
        on g.h3_cell = c.h3_cell
    left join {{ ref('int_bathymetry') }} b
        on g.h3_cell = b.h3_cell
    left join {{ ref('int_mpa_coverage') }} m
        on g.h3_cell = m.h3_cell
    left join {{ ref('int_proximity') }} p
        on g.h3_cell = p.h3_cell
    left join {{ ref('int_ship_strike_density') }} ss
        on g.h3_cell = ss.h3_cell
    left join {{ ref('int_speed_zone_coverage') }} sz
        on g.h3_cell = sz.h3_cell
    left join {{ ref('int_nisi_reference_risk') }} nr
        on g.h3_cell = nr.h3_cell
    left join {{ ref('int_ocean_covariates') }} oc
        on g.h3_cell = oc.h3_cell

    -- Exclude land cells (GEBCO positive = above sea level)
    where coalesce(b.is_land, false) = false

),

ranked as (

    -- Percentile-rank each risk-relevant feature (0 = safest, 1 = most dangerous)
    -- percent_rank() handles ties and gives a uniform 0–1 distribution.
    -- Features with NULL or 0 are coalesced to 0 so they rank at the bottom.
    select
        *,

        -- Traffic percentiles
        percent_rank() over (order by coalesce(avg_monthly_vessels, 0))
            as pctl_vessels,
        percent_rank() over (order by coalesce(avg_speed_lethality, 0))
            as pctl_speed_lethality,
        percent_rank() over (order by coalesce(avg_large_vessels, 0))
            as pctl_large_vessels,
        percent_rank() over (order by coalesce(avg_draft_imputed_m, 0))
            as pctl_draft_risk,
        percent_rank() over (order by coalesce(avg_high_speed_fraction, 0))
            as pctl_high_speed_fraction,
        percent_rank() over (order by coalesce(avg_draft_risk_fraction, 0))
            as pctl_draft_risk_fraction,
        percent_rank() over (order by coalesce(avg_commercial_vessels, 0))
            as pctl_commercial,
        percent_rank() over (order by coalesce(avg_night_vessels, 0))
            as pctl_night_traffic,

        -- Cetacean percentiles
        percent_rank() over (order by coalesce(total_sightings, 0))
            as pctl_sightings,
        percent_rank() over (order by coalesce(baleen_whale_sightings, 0))
            as pctl_baleen,
        percent_rank() over (order by coalesce(recent_sightings, 0))
            as pctl_recent_sightings,

        -- Strike history percentiles
        percent_rank() over (order by coalesce(total_strikes, 0))
            as pctl_strikes,
        percent_rank() over (order by coalesce(fatal_strikes, 0))
            as pctl_fatal_strikes,
        percent_rank() over (order by coalesce(baleen_strikes, 0))
            as pctl_baleen_strikes,

        -- Nisi reference risk percentile
        percent_rank() over (order by coalesce(nisi_all_risk, 0))
            as pctl_nisi_risk

    from features

),

scored as (

    select
        *,

        -- ── Traffic threat sub-score (0–1) ────────────
        -- V&T speed-lethality + high-speed fraction (speed risk),
        -- vessel volume, size, draft (continuous + fraction),
        -- commercial vessel type, and night traffic.
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

        -- ── Cetacean exposure sub-score (0–1) ─────────
        -- Captures whale presence and vulnerability
        (
            0.35 * pctl_sightings
          + 0.35 * pctl_baleen
          + 0.30 * pctl_recent_sightings
        ) as cetacean_score,

        -- ── Strike history sub-score (0–1) ────────────
        -- Historical collision record in this cell
        -- Fatal and baleen strikes get extra weight
        (
            0.40 * pctl_strikes
          + 0.35 * pctl_fatal_strikes
          + 0.25 * pctl_baleen_strikes
        ) as strike_score,

        -- ── Habitat suitability sub-score (0–1) ───────
        -- Continental shelf and shelf-edge are prime whale habitat
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

        -- ── Protection gap sub-score (0–1) ────────────
        -- Higher = less protected = more risk
        -- MPA and speed zone coverage mitigate collision risk
        case
            when coalesce(in_current_sma, false) and coalesce(has_no_take_zone, false)
                then 0.1   -- Best: SMA + no-take MPA
            when coalesce(in_current_sma, false)
                then 0.2   -- Active speed restriction
            when coalesce(in_proposed_zone, false) and in_mpa
                then 0.3   -- Proposed speed zone + MPA
            when coalesce(has_no_take_zone, false)
                then 0.3   -- No-take MPA
            when coalesce(in_proposed_zone, false)
                then 0.4   -- Proposed speed zone (not yet active)
            when coalesce(has_strict_protection, false)
                then 0.5   -- Strict MPA
            when in_mpa
                then 0.7   -- Some MPA coverage
            else 1.0       -- No protection at all
        end as protection_gap,

        -- ── Proximity sub-score (0–1) ─────────────────
        -- Blends co-location of whales/ships with proximity
        -- to known strike sites and distance from protection.
        -- Whale-ship overlap is the primary signal; strike
        -- proximity and protection gap add spatial context.
        (
            0.45 * sqrt(
                coalesce(whale_proximity_score, 0)
              * coalesce(ship_proximity_score, 0)
            )
          + 0.30 * coalesce(strike_proximity_score, 0)
          + 0.25 * (1.0 - coalesce(protection_proximity_score, 0))
        ) as proximity_score,

        -- ── Reference risk sub-score (0–1) ────────────
        -- Nisi et al. 2024 published risk as external benchmark
        pctl_nisi_risk as reference_risk_score

    from ranked

)

select
    h3_cell,
    cell_lat,
    cell_lon,
    geom,

    -- ── Composite risk score ────────────────────────
    -- 7 sub-scores weighted to 1.0
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

    -- ── Sub-scores (for interpretability) ───────────
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
    has_nisi_reference,

    -- ── Traffic features ────────────────────────────
    months_active,
    total_pings,
    avg_monthly_vessels,
    peak_monthly_vessels,
    avg_speed_knots,
    peak_speed_knots,
    avg_high_speed_vessels,
    total_high_speed_pings,
    avg_large_vessels,
    avg_vessel_length_m,
    avg_deep_draft_vessels,
    avg_speed_lethality,
    avg_high_speed_fraction,
    avg_draft_risk_fraction,
    avg_cog_diversity,
    avg_night_vessels,
    avg_night_high_speed,
    night_traffic_ratio,
    avg_commercial_vessels,
    avg_fishing_vessels,
    avg_passenger_vessels,

    -- ── Cetacean features ───────────────────────────
    total_sightings,
    unique_species,
    species_level_sightings,
    recent_sightings,
    baleen_whale_sightings,
    sighting_earliest_year,
    sighting_latest_year,

    -- ── Strike history features ─────────────────────
    total_strikes,
    fatal_strikes,
    serious_injury_strikes,
    baleen_strikes,
    right_whale_strikes,
    strike_species_groups,
    strike_species_list,

    -- ── Speed zone features ─────────────────────────
    zone_count,
    max_season_days,
    zone_names,

    -- ── Nisi reference features ─────────────────────
    nisi_all_risk,
    nisi_shipping_index,
    nisi_whale_space_use,
    nisi_hotspot_overlap,
    nisi_dist_km,

    -- ── Ocean covariate features ────────────────────
    sst,
    sst_sd,
    mld,
    sla,
    pp_upper_200m,

    -- ── Bathymetry features ─────────────────────────
    depth_m,
    depth_range_m,
    is_continental_shelf,
    is_shelf_edge,
    depth_zone,

    -- ── MPA features ────────────────────────────────
    mpa_count,
    has_strict_protection,
    has_no_take_zone,

    -- ── Proximity features ──────────────────────────
    dist_to_nearest_whale_km,
    dist_to_nearest_ship_km,
    dist_to_nearest_strike_km,
    dist_to_nearest_protection_km

from scored
