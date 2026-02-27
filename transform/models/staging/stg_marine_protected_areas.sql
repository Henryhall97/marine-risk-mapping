-- Staging model: marine protected areas
-- Cleans and standardises the raw NOAA MPA Inventory data.
--
-- What this does:
--   1. Fixes invalid geometries with ST_MakeValid()
--   2. Filters to marine MPAs only (MarPercent > 0)
--   3. Renames columns to snake_case
--   4. Replaces sentinel values (Estab_Yr = 0 → NULL)

with source as (

    select * from {{ source('marine_risk', 'marine_protected_areas') }}

),

cleaned as (

    select
        id,
        site_id,
        site_name,
        gov_level,
        state,
        prot_lvl       as protection_level,
        mgmt_agen      as managing_agency,
        iucn_cat       as iucn_category,

        -- Replace sentinel 0 with NULL (0 = unknown year)
        nullif(estab_yr, 0) as established_year,

        area_km        as area_total_km2,
        area_mar       as area_marine_km2,
        mar_percent    as marine_percent,

        -- Fix the 55 invalid geometries we found in the
        -- quality report (self-intersections, ring errors)
        ST_MakeValid(geom) as geom

    from source

    -- Keep only MPAs with some marine component
    where mar_percent > 0

)

select * from cleaned
