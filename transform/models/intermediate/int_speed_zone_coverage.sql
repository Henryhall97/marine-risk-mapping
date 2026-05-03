-- Intermediate model: speed zone coverage per hex cell
-- Identifies which H3 cells overlap with NARW speed
-- management zones (both proposed and current SMAs).

{{ config(
    indexes=[
        {'columns': ['h3_cell']},
    ]
) }}

--
-- Uses ST_Intersects between cell centroid and zone polygons.
-- A cell can overlap multiple zones with different seasons.
--
-- Grain: one row per h3_cell.

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
        start_day,
        end_month,
        end_day,
        season_days,
        season_label,
        geom
    from {{ ref('stg_speed_zones') }}

),

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

cell_summary as (

    select
        h3_cell,

        -- Any speed zone coverage?
        true                                    as in_speed_zone,

        -- Current active SMA coverage
        bool_or(source_type = 'current_sma')    as in_current_sma,

        -- Proposed zone coverage
        bool_or(source_type = 'proposed')        as in_proposed_zone,

        -- Count of overlapping zones
        count(*)                                as zone_count,
        count(*) filter (
            where source_type = 'current_sma'
        )                                       as current_sma_count,

        -- Maximum season length (days of speed restriction)
        max(season_days)                        as max_season_days,

        -- Total months covered by any speed restriction
        -- (approximate — counts distinct start months)
        count(distinct start_month)             as restricted_start_months,

        -- Zone names for reference
        string_agg(
            zone_name || ' (' || source_type || ')',
            '; ' order by zone_name || ' (' || source_type || ')'
        )                                       as zone_names,

        -- Season labels
        string_agg(
            zone_name || ': ' || season_label,
            '; ' order by zone_name || ': ' || season_label
        )                                       as season_labels

    from cell_zones
    group by h3_cell

)

select * from cell_summary
