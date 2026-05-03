-- Intermediate model: Nisi et al. (2024) reference risk
-- Spatially joins each H3 hex cell to the nearest Nisi risk
-- grid cell to pull in their published risk scores as a
-- benchmark/reference layer.

{{ config(
    indexes=[
        {'columns': ['h3_cell']},
    ]
) }}

--
-- Nisi's grid is 1-degree — much coarser than our H3 res-7
-- (~1.2km). We use ST_DWithin with a 1-degree threshold to
-- find the nearest Nisi cell and cross-join its risk values.
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

nisi as (

    select
        lat,
        lon,
        all_risk,
        shipping_index,
        all_space_use,
        blue_risk,
        fin_risk,
        humpback_risk,
        sperm_risk,
        mgmt,
        mgmt_mandatory,
        hotspot_overlap,
        geom
    from {{ ref('stg_nisi_risk_grid') }}

),

-- Use LATERAL join to find nearest Nisi cell per H3 cell
-- This is efficient with a GiST index on nisi_risk_grid.geom
nearest_nisi as (

    select distinct on (g.h3_cell)
        g.h3_cell,
        n.all_risk           as nisi_all_risk,
        n.shipping_index     as nisi_shipping_index,
        n.all_space_use      as nisi_whale_space_use,
        n.blue_risk          as nisi_blue_risk,
        n.fin_risk           as nisi_fin_risk,
        n.humpback_risk      as nisi_humpback_risk,
        n.sperm_risk         as nisi_sperm_risk,
        n.mgmt               as nisi_has_management,
        n.mgmt_mandatory     as nisi_has_mandatory_mgmt,
        n.hotspot_overlap     as nisi_hotspot_overlap,
        ST_Distance(g.geom::geography, n.geom::geography) / 1000.0
                             as nisi_dist_km

    from grid g
    inner join nisi n
        on ST_DWithin(g.geom, n.geom, {{ var('nisi_match_degrees') }})  -- degree threshold
    order by g.h3_cell, ST_Distance(g.geom, n.geom)

)

select * from nearest_nisi
