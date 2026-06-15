-- Staging model: CMIP6 projected ocean covariates
-- Cleans and standardises the climate-projected ocean
-- environmental data (SST, MLD, SLA, primary productivity)
-- for downstream spatial joins to the hex grid.
--
-- Same structure as stg_ocean_covariates but with additional
-- scenario and decade columns for CMIP6 projections.

with source as (

    select * from {{ source('marine_risk', 'cmip6_ocean_covariates') }}

),

cleaned as (

    select
        id,
        lat,
        lon,
        season,
        scenario,
        decade,

        -- Environmental covariates
        sst,
        sst_sd,
        mld,
        sla,
        pp_upper_200m,

        -- Point geometry for spatial joins
        coalesce(
            geom,
            ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        ) as geom

    from source

    -- Exclude rows where ALL covariates are null
    where sst is not null
       or mld is not null
       or sla is not null
       or pp_upper_200m is not null

),

-- Dedupe: a few CMIP6 model grid cells round to the same 0.5-degree
-- (lat, lon) within a (scenario, decade, season), which would otherwise
-- multiply rows in the downstream equi-join on (lat, lon) and break the
-- (h3_cell, season, scenario, decade) uniqueness of
-- int_ocean_covariates_projected. Keep one row per coordinate.
deduped as (

    select distinct on (scenario, decade, season, lat, lon)
        *
    from cleaned
    order by scenario, decade, season, lat, lon, id

)

select * from deduped
