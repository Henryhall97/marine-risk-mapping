-- Intermediate model: bathymetry per hex cell
-- Reads pre-sampled GEBCO depth values from bathymetry_h3
-- (produced by pipeline/aggregation/sample_bathymetry.py).
--
-- Each cell has depth averaged across 7 points (centroid + 6
-- hexagon vertices) to capture shelf-edge gradients.
--
-- Adds derived features for the risk model:
--   - depth_zone: shelf / slope / abyssal classification
--   - is_continental_shelf: boolean for primary whale habitat
--   - is_shelf_edge: cells straddling the 200m contour
--   - is_ocean: authoritative ocean flag from Natural Earth polygon
--     (replaces naive depth_m >= 0 that misclassifies Great Lakes)
--
-- Grain: one row per h3_cell.

select
    b.h3_cell,

    -- Raw depth (negative = below sea level, positive = land)
    b.depth_m,
    b.min_depth_m,
    b.max_depth_m,
    b.depth_range_m,
    b.sample_count,

    -- Legacy land flag (kept for backward compat; prefer is_ocean)
    b.depth_m >= 0 as is_land,

    -- Ocean mask: true if cell centroid falls within a Natural Earth
    -- ocean polygon. Correctly excludes Great Lakes, rivers, and
    -- other inland water bodies that have negative GEBCO depth.
    exists (
        select 1
        from {{ source('marine_risk', 'ocean_mask') }} om
        where ST_Intersects(
            ST_SetSRID(ST_MakePoint(g.cell_lon, g.cell_lat), 4326),
            om.geom
        )
    ) as is_ocean,

    -- Continental shelf: primary whale feeding habitat
    -- GEBCO uses negative values for below sea level
    -- Must exclude land (depth_m >= 0) which also passes >= {{ var('shelf_depth_m') }}
    (b.depth_m >= {{ var('shelf_depth_m') }} and b.depth_m < 0) as is_continental_shelf,

    -- Shelf edge: depth range crosses the {{ var('shelf_depth_m') }}m contour
    -- These are upwelling zones where whales concentrate
    (b.min_depth_m < {{ var('shelf_depth_m') }} and b.max_depth_m >= {{ var('shelf_depth_m') }}) as is_shelf_edge,

    -- Depth zone classification
    case
        when b.depth_m >= 0     then 'land'
        when b.depth_m >= {{ var('shelf_depth_m') }}  then 'shelf'
        when b.depth_m >= {{ var('slope_depth_m') }} then 'slope'
        else 'abyssal'
    end as depth_zone

from {{ source('marine_risk', 'bathymetry_h3') }} b
inner join {{ ref('int_hex_grid') }} g
    on b.h3_cell = g.h3_cell
