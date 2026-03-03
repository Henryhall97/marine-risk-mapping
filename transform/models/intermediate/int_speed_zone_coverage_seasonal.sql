-- Intermediate model: speed zone coverage per hex cell per season
-- Determines whether each speed zone is ACTIVE during each season.
--
-- A zone is considered active in a season if any month in that
-- season falls within the zone's [start_month, end_month] range.
-- Handles year-wrapping zones (e.g., Nov 1 – Apr 30).
--
-- Grain: one row per (h3_cell, season).

with grid as (

    select
        h3_cell,
        geom
    from {{ ref('int_hex_grid') }}

),

zones as (

    select
        zone_name,
        zone_abbr,
        source_type,
        start_month,
        end_month,
        season_days,
        season_label,
        geom
    from {{ ref('stg_speed_zones') }}

),

-- All 4 seasons with their month lists
seasons as (
    select 'winter' as season, unnest(array{{ var('season_winter_months') }}) as m
    union all
    select 'spring', unnest(array{{ var('season_spring_months') }})
    union all
    select 'summer', unnest(array{{ var('season_summer_months') }})
    union all
    select 'fall', unnest(array{{ var('season_fall_months') }})
),

-- Which cells overlap which zones (spatial join — same as static model)
cell_zones as (

    select
        g.h3_cell,
        z.zone_name,
        z.zone_abbr,
        z.source_type,
        z.start_month,
        z.end_month,
        z.season_days,
        z.season_label
    from grid g
    inner join zones z
        on ST_Intersects(g.geom, z.geom)

),

-- Determine which (zone, season) combos are active
-- A zone is active in a season if any season month falls
-- in the zone's active range, handling year-wrapping.
zone_season_active as (

    select distinct
        cz.h3_cell,
        s.season,
        cz.zone_name,
        cz.zone_abbr,
        cz.source_type,
        cz.season_days
    from cell_zones cz
    cross join seasons s
    where
        -- Non-wrapping: start_month <= end_month (e.g., Mar–Jul)
        (cz.start_month <= cz.end_month
         and s.m between cz.start_month and cz.end_month)
        or
        -- Year-wrapping: start_month > end_month (e.g., Nov–Apr)
        (cz.start_month > cz.end_month
         and (s.m >= cz.start_month or s.m <= cz.end_month))

),

cell_season_summary as (

    select
        h3_cell,
        season,

        -- Any speed zone active this season?
        true                                    as in_speed_zone,

        -- Current active SMA
        bool_or(source_type = 'current_sma')    as in_current_sma,

        -- Proposed zone
        bool_or(source_type = 'proposed')        as in_proposed_zone,

        -- Count of active zones this season
        count(distinct zone_name)               as zone_count,
        count(distinct zone_name) filter (
            where source_type = 'current_sma'
        )                                       as current_sma_count,

        -- Maximum season length among active zones
        max(season_days)                        as max_season_days,

        -- Zone names for reference
        string_agg(
            distinct zone_name || ' (' || source_type || ')',
            '; ' order by zone_name || ' (' || source_type || ')'
        )                                       as zone_names

    from zone_season_active
    group by h3_cell, season

)

select * from cell_season_summary
