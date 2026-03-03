-- Intermediate model: ocean covariates per hex cell (annual mean)
-- Spatially joins ocean environmental data to the H3 hex grid
-- using nearest-neighbour matching.
--
-- The source data is now seasonal (4 seasons per grid point).
-- This model averages across all 4 seasons to produce a single
-- annual-mean row per H3 cell, preserving backward compatibility
-- with static (non-seasonal) downstream models.
--
-- For seasonal ocean covariates, use int_ocean_covariates_seasonal.
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
        season,
        sst,
        sst_sd,
        mld,
        sla,
        pp_upper_200m,
        geom
    from {{ ref('stg_ocean_covariates') }}

),

-- Average seasonal values back to annual mean per grid point
annual_covariates as (

    select
        lat,
        lon,
        avg(sst)           as sst,
        avg(sst_sd)        as sst_sd,
        avg(mld)           as mld,
        avg(sla)           as sla,
        avg(pp_upper_200m) as pp_upper_200m,
        -- All 4 season rows share the same geom; pick any via first_value
        (array_agg(geom))[1] as geom
    from covariates
    group by lat, lon

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
    inner join annual_covariates c
        on ST_DWithin(g.geom, c.geom, {{ var('ocean_covariate_match_degrees') }})  -- degree threshold
    order by g.h3_cell, ST_Distance(g.geom, c.geom)

)

select * from nearest_cov
