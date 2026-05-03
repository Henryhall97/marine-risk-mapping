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

)

select * from cleaned
