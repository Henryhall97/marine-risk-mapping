-- Staging model: ocean covariates
-- Cleans and standardises the ocean environmental data
-- (SST, MLD, SLA, primary productivity) for downstream
-- spatial joins to the hex grid.
--
-- What this does:
--   1. Selects environmental columns
--   2. Filters out rows with all-null covariates (land cells)
--   3. Creates a point geometry for spatial joins

with source as (

    select * from {{ source('marine_risk', 'ocean_covariates') }}

),

cleaned as (

    select
        id,
        lat,
        lon,

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

    -- Exclude rows where ALL covariates are null (land cells)
    where sst is not null
       or mld is not null
       or sla is not null
       or pp_upper_200m is not null

)

select * from cleaned
