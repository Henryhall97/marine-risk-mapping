-- Intermediate model: H3 hex grid spine
-- One row per unique H3 resolution-7 cell (~1.2km).
--
-- UNIONs cells from all data sources so the grid covers:
--   1. AIS vessel traffic cells (~1.9M)
--   2. Cetacean sighting cells (some outside shipping lanes)
--   3. Ship strike cells (historically dangerous locations)
--
-- This ensures the mart-layer risk model can LEFT JOIN
-- all data domains without losing any spatially-relevant cells.
--
-- Creates a PostGIS POINT geometry from the cell centroid
-- for downstream spatial joins (MPA overlay, speed zones, etc.).

{{ config(
    indexes=[
        {'columns': ['h3_cell']},
        {'columns': ['cell_lat', 'cell_lon']},
        {'columns': ['geom'], 'type': 'gist'},
    ]
) }}

with ais_cells as (

    select distinct
        h3_cell,
        cell_lat,
        cell_lon
    from {{ source('marine_risk', 'ais_h3_summary') }}

),

cetacean_cells as (

    select distinct
        h3_cell,
        cell_lat,
        cell_lon
    from {{ source('marine_risk', 'cetacean_sighting_h3') }}

),

strike_cells as (

    select distinct
        h3_cell,
        cell_lat,
        cell_lon
    from {{ source('marine_risk', 'ship_strike_h3') }}

),

all_cells as (

    select * from ais_cells
    union
    select * from cetacean_cells
    union
    select * from strike_cells

)

select
    h3_cell,
    cell_lat,
    cell_lon,
    ST_SetSRID(ST_MakePoint(cell_lon, cell_lat), 4326) as geom

from all_cells
