-- Intermediate model: projected ocean covariates per hex cell
-- Spatially joins CMIP6 climate-projected ocean environmental data
-- to the H3 hex grid using nearest-neighbour matching.
--
-- Optimised two-step approach:
--   Step 1: Spatial NN on just ONE (scenario, decade, season) combo
--           (~109K covariate points → ~1.1M grid matches).
--   Step 2: Equi-join matched lat/lon back to ALL 32 combos.
-- This avoids 32× redundant spatial work since the CMIP6 data uses
-- the same lat/lon grid for every (scenario, decade, season).
--
-- Grain: one row per (h3_cell, season, scenario, decade).

{{ config(
    materialized='table',
    indexes=[
        {'columns': ['h3_cell', 'season', 'scenario', 'decade']},
    ]
) }}

-- Step 1: spatial nearest-neighbour using one arbitrary combo
-- (ssp245 / 2030s / winter ≈ 109K points).  All combos share
-- the same lat/lon grid, so the match is valid for all.
with nn_lookup as (

    select distinct on (g.h3_cell)
        g.h3_cell,
        c.lat  as match_lat,
        c.lon  as match_lon,
        ST_Distance(g.geom::geography, c.geom::geography) / 1000.0
                     as covariate_dist_km
    from {{ ref('int_hex_grid') }} g
    inner join {{ ref('stg_cmip6_ocean_covariates') }} c
        on ST_DWithin(
            g.geom, c.geom,
            {{ var('ocean_covariate_match_degrees') }}
        )
    where c.scenario = 'ssp245'
      and c.decade   = '2030s'
      and c.season   = 'winter'
    order by g.h3_cell, ST_Distance(g.geom, c.geom)

)

-- Step 2: expand to all 32 combos via equi-join on (lat, lon)
select
    nn.h3_cell,
    cv.season,
    cv.scenario,
    cv.decade,
    cv.sst,
    cv.sst_sd,
    cv.mld,
    cv.sla,
    cv.pp_upper_200m,
    nn.covariate_dist_km

from nn_lookup nn
inner join {{ ref('stg_cmip6_ocean_covariates') }} cv
    on  cv.lat = nn.match_lat
    and cv.lon = nn.match_lon
