-- Intermediate model: ocean covariates per hex cell
-- Spatially joins ocean environmental data to the H3 hex grid
-- using nearest-neighbour matching.
--
-- Ocean covariate grid (~0.08–0.25°) is coarser than H3 res-7
-- (~1.2km), so multiple H3 cells map to the same covariate point.
-- We pick the nearest covariate point within 0.3 degrees.
--
-- Grain: one row per h3_cell.

with grid as (

    select
        h3_cell,
        cell_lat,
        cell_lon,
        geom
    from {{ ref('int_hex_grid') }}

),

covariates as (

    select
        lat,
        lon,
        sst,
        sst_sd,
        mld,
        sla,
        pp_upper_200m,
        geom
    from {{ ref('stg_ocean_covariates') }}

),

-- Nearest-neighbour join: pick closest covariate point per H3 cell
nearest_cov as (

    select distinct on (g.h3_cell)
        g.h3_cell,
        c.sst,
        c.sst_sd,
        c.mld,
        c.sla,
        c.pp_upper_200m,
        ST_Distance(g.geom::geography, c.geom::geography) / 1000.0
                             as covariate_dist_km

    from grid g
    inner join covariates c
        on ST_DWithin(g.geom, c.geom, 0.3)  -- 0.3 degree threshold
    order by g.h3_cell, ST_Distance(g.geom, c.geom)

)

select * from nearest_cov
