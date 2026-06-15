-- Intermediate model: right whale slow-zone coverage per hex cell
-- Identifies which H3 cells overlap active NOAA Fisheries Dynamic
-- Management Areas (DMAs) / slow zones using ST_Intersects between
-- the cell footprint and the slow-zone polygons.
--
-- Phase 1b item (H): slow zones are voluntary 10-knot advisories
-- triggered by NARW detections.  Their enforceability is comparable
-- to voluntary SMAs, so they contribute a small protection bonus in
-- the protection-gap sub-score (not as strong as MPAs / critical
-- habitat).  All current DMAs are voluntary.
--
-- Grain: one row per h3_cell (only cells that overlap a slow zone).

{{ config(
    indexes=[
        {'columns': ['h3_cell']},
    ]
) }}

with grid as (

    select
        h3_cell,
        geom
    from {{ ref('int_hex_grid') }}

),

slow_zones as (

    select
        zone_name,
        voluntary,
        geom
    from {{ source('marine_risk', 'right_whale_slow_zones') }}

),

cell_slow_zone as (

    select
        g.h3_cell,

        count(*)                                  as slow_zone_count,

        string_agg(
            distinct s.zone_name, '; '
            order by s.zone_name
        )                                         as slow_zone_names,

        true                                      as in_slow_zone

    from grid g
    inner join slow_zones s
        on ST_Intersects(g.geom, s.geom)
    group by g.h3_cell

)

select * from cell_slow_zone
