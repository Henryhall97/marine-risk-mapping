-- Intermediate model: MPA coverage per hex cell
-- Identifies which H3 cells overlap with Marine Protected Areas
-- using ST_Intersects between cell centroid and MPA polygons.
--
-- Aggregates to one row per cell: a cell that overlaps 3 MPAs
-- gets mpa_count = 3 with the highest protection level.
--
-- The GiST index on marine_protected_areas.geom makes the
-- spatial join efficient (843 polygons × ~1.9M points, but
-- index filters to only nearby candidates).
--
-- Grain: one row per h3_cell.

with grid as (

    select
        h3_cell,
        geom
    from {{ ref('int_hex_grid') }}

),

mpas as (

    select
        site_id,
        site_name,
        protection_level,
        iucn_category,
        geom
    from {{ ref('stg_marine_protected_areas') }}

),

cell_mpa as (

    select
        g.h3_cell,

        -- How many MPAs overlap this cell?
        count(*)                              as mpa_count,

        -- MPA names (for reference / debugging)
        string_agg(
            distinct m.site_name, '; '
            order by m.site_name
        )                                     as mpa_names,

        -- IUCN strict protection (categories I–III)
        bool_or(
            m.iucn_category in ('Ia', 'Ib', 'II', 'III')
        )                                     as has_strict_protection,

        -- Any no-take zone?
        bool_or(
            m.protection_level in ('No Take', 'No Access', 'No Impact')
        )                                     as has_no_take_zone

    from grid g
    inner join mpas m
        on ST_Intersects(g.geom, m.geom)
    group by g.h3_cell

)

select * from cell_mpa
