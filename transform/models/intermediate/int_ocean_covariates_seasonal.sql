-- Intermediate model: seasonal ocean covariates per hex cell
-- Spatially joins seasonal ocean environmental data to the H3 hex grid
-- using nearest-neighbour matching — same approach as int_ocean_covariates
-- but at (h3_cell, season) grain.
--
-- Ocean covariates now carry a season column (climatological seasonal
-- means from 2019–2024), so SST, MLD, SLA, and PP all vary by season.
--
-- Grain: one row per (h3_cell, season).

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

-- Nearest-neighbour join per season: pick closest covariate point
-- for each H3 cell within each season.
-- The spatial grid is the same for all 4 seasons (same lat/lon points),
-- so we use DISTINCT ON (h3_cell, season) ordered by distance.
nearest_cov as (

    select distinct on (g.h3_cell, c.season)
        g.h3_cell,
        c.season,
        c.sst,
        c.sst_sd,
        c.mld,
        c.sla,
        c.pp_upper_200m,
        ST_Distance(g.geom::geography, c.geom::geography) / 1000.0
                             as covariate_dist_km

    from grid g
    inner join covariates c
        on ST_DWithin(g.geom, c.geom, {{ var('ocean_covariate_match_degrees') }})
    order by g.h3_cell, c.season, ST_Distance(g.geom, c.geom)

)

select * from nearest_cov
