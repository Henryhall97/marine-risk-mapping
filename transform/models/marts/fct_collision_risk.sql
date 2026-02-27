-- Mart model: whale–vessel collision risk per H3 cell
--
-- Joins all intermediate domains onto the hex grid and computes
-- a composite risk score on a 0–1 scale (higher = more dangerous).
--
-- Methodology:
--   1. Aggregate monthly vessel traffic to per-cell summaries
--   2. LEFT JOIN traffic, cetacean, bathymetry, MPA, proximity
--   3. Percentile-rank each risk-relevant feature (0–1)
--   4. Combine into five sub-scores via weighted average
--   5. Final score = weighted sum of sub-scores
--
-- Sub-score weights:
--   - Traffic threat      30%  (vessel density, speed, size)
--   - Cetacean exposure   30%  (sighting density, vulnerability)
--   - Proximity           20%  (co-location of whales and ships)
--   - Habitat suitability 10%  (shelf, shelf edge, depth)
--   - Protection gap      10%  (inverse of MPA coverage)
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

        -- Proximity features (distance to nearest whale / ship)
        p.dist_to_nearest_whale_km,
        p.dist_to_nearest_ship_km,
        p.whale_proximity_score,
        p.ship_proximity_score,

        -- Convenience booleans
        t.h3_cell is not null      as has_traffic,
        c.h3_cell is not null      as has_whale_sightings,
        m.h3_cell is not null      as in_mpa

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
        percent_rank() over (order by coalesce(avg_high_speed_vessels, 0))
            as pctl_high_speed,
        percent_rank() over (order by coalesce(avg_large_vessels, 0))
            as pctl_large_vessels,
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
            as pctl_recent_sightings

    from features

),

scored as (

    select
        *,

        -- ── Traffic threat sub-score (0–1) ────────────
        -- Captures how much vessel activity threatens whales
        (
            0.35 * pctl_vessels
          + 0.25 * pctl_high_speed
          + 0.20 * pctl_large_vessels
          + 0.10 * pctl_commercial
          + 0.10 * pctl_night_traffic
        ) as traffic_score,

        -- ── Cetacean exposure sub-score (0–1) ─────────
        -- Captures whale presence and vulnerability
        (
            0.35 * pctl_sightings
          + 0.35 * pctl_baleen
          + 0.30 * pctl_recent_sightings
        ) as cetacean_score,

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
        -- MPA presence mitigates collision risk via speed restrictions
        case
            when coalesce(has_no_take_zone, false)     then 0.2
            when coalesce(has_strict_protection, false) then 0.4
            when in_mpa                                then 0.7
            else 1.0
        end as protection_gap,

        -- ── Proximity sub-score (0–1) ─────────────────
        -- High when whales and ships are close together.
        -- Uses exponential decay scores (10km half-life):
        --   whale_proximity_score = how close is nearest whale?
        --   ship_proximity_score  = how close is nearest ship?
        -- Geometric mean captures the co-location signal:
        -- both must be close for the score to be high.
        sqrt(
            coalesce(whale_proximity_score, 0)
          * coalesce(ship_proximity_score, 0)
        ) as proximity_score

    from ranked

)

select
    h3_cell,
    cell_lat,
    cell_lon,
    geom,

    -- ── Composite risk score ────────────────────────
    round((
        0.30 * traffic_score
      + 0.30 * cetacean_score
      + 0.20 * proximity_score
      + 0.10 * habitat_score
      + 0.10 * protection_gap
    )::numeric, 4) as risk_score,

    -- ── Risk category ───────────────────────────────
    case
        when (
            0.30 * traffic_score
          + 0.30 * cetacean_score
          + 0.20 * proximity_score
          + 0.10 * habitat_score
          + 0.10 * protection_gap
        ) >= 0.7  then 'critical'
        when (
            0.30 * traffic_score
          + 0.30 * cetacean_score
          + 0.20 * proximity_score
          + 0.10 * habitat_score
          + 0.10 * protection_gap
        ) >= 0.5  then 'high'
        when (
            0.30 * traffic_score
          + 0.30 * cetacean_score
          + 0.20 * proximity_score
          + 0.10 * habitat_score
          + 0.10 * protection_gap
        ) >= 0.35 then 'medium'
        when (
            0.30 * traffic_score
          + 0.30 * cetacean_score
          + 0.20 * proximity_score
          + 0.10 * habitat_score
          + 0.10 * protection_gap
        ) >= 0.2  then 'low'
        else 'minimal'
    end as risk_category,

    -- ── Sub-scores (for interpretability) ───────────
    round(traffic_score::numeric, 4)    as traffic_score,
    round(cetacean_score::numeric, 4)   as cetacean_score,
    round(proximity_score::numeric, 4)  as proximity_score,
    round(habitat_score::numeric, 4)    as habitat_score,
    round(protection_gap::numeric, 4)   as protection_gap,

    -- ── Feature flags ───────────────────────────────
    has_traffic,
    has_whale_sightings,
    in_mpa,

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
    dist_to_nearest_ship_km

from scored
