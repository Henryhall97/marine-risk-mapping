-- Intermediate model: whale critical-habitat coverage per hex cell
-- Identifies which H3 cells overlap NMFS ESA-designated critical
-- habitat using ST_Intersects between the cell centroid/footprint
-- and the critical-habitat polygons.
--
-- Phase 1b item (H): critical habitat is strong, enforceable spatial
-- protection (ESA § 4) and feeds the protection-gap sub-score.  Only
-- FINAL-designated units count — the single Proposed unit
-- (is_proposed = true) is excluded because it is not yet enforceable.
--
-- Grain: one row per h3_cell (only cells that overlap habitat).

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

habitat as (

    select
        species_label,
        cmn_name,
        geom
    from {{ source('marine_risk', 'whale_critical_habitat') }}
    -- Final designations only — exclude proposed (not enforceable)
    where coalesce(is_proposed, false) = false

),

cell_habitat as (

    select
        g.h3_cell,

        count(*)                                  as critical_habitat_count,

        string_agg(
            distinct h.cmn_name, '; '
            order by h.cmn_name
        )                                         as critical_habitat_species,

        true                                      as in_critical_habitat

    from grid g
    inner join habitat h
        on ST_Intersects(g.geom, h.geom)
    group by g.h3_cell

)

select * from cell_habitat
