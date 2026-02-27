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
--
-- Grain: one row per h3_cell.

select
    h3_cell,

    -- Raw depth (negative = below sea level, positive = land)
    depth_m,
    min_depth_m,
    max_depth_m,
    depth_range_m,
    sample_count,

    -- Land flag: positive GEBCO values are above sea level
    depth_m >= 0 as is_land,

    -- Continental shelf: primary whale feeding habitat
    -- GEBCO uses negative values for below sea level
    -- Must exclude land (depth_m >= 0) which also passes >= -200
    (depth_m >= -200 and depth_m < 0) as is_continental_shelf,

    -- Shelf edge: depth range crosses the -200m contour
    -- These are upwelling zones where whales concentrate
    (min_depth_m < -200 and max_depth_m >= -200) as is_shelf_edge,

    -- Depth zone classification
    case
        when depth_m >= 0     then 'land'
        when depth_m >= -200  then 'shelf'
        when depth_m >= -1000 then 'slope'
        else 'abyssal'
    end as depth_zone

from {{ source('marine_risk', 'bathymetry_h3') }}
