-- Staging model: Nisi et al. (2024) whale-ship risk grid
-- Cleans and standardises the global 1-degree risk grid for
-- use as a reference/benchmark in downstream models.
--
-- What this does:
--   1. Selects key risk columns and species-level scores
--   2. Filters to cells overlapping the study bounding box
--   3. Renames columns for consistency

with source as (

    select * from {{ source('marine_risk', 'nisi_risk_grid') }}

),

cleaned as (

    select
        -- Location
        x             as lon,
        y             as lat,
        region,
        geom,

        -- Combined risk metrics
        all_risk,
        shipping_index,            -- shipping intensity (threat proxy)
        all_space_use,             -- whale space-use (vulnerability proxy)
        hotspot_overlap,           -- count of species hotspots overlapping

        -- Species-level risk scores (risk = shipping × whale space-use)
        blue_risk,
        fin_risk,
        humpback_risk,
        sperm_risk,

        -- Species-level occurrence & space-use
        blue_mean_occurrence,
        blue_space_use,
        fin_mean_occurrence,
        fin_space_use,
        humpback_mean_occurrence,
        humpback_space_use,
        sperm_mean_occurrence,
        sperm_space_use,

        -- Management indicators
        mgmt,
        mgmt_mandatory,

        -- Species-level hotspot flags (top 1% risk cells)
        blue_hotspot_99,
        fin_hotspot_99,
        humpback_hotspot_99,
        sperm_hotspot_99

    from source

    -- Filter to cells that intersect the study bbox
    -- Nisi grid is global — keep only relevant cells
    -- Matches US_BBOX in pipeline/config.py
    where x between -180 and -59
      and y between -2 and 52

)

select * from cleaned
