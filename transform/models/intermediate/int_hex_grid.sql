-- Intermediate model: H3 hex grid spine
-- One row per unique H3 resolution-7 cell (~1.2km).
--
-- UNIONs cells from all data sources so the grid covers:
--   1. AIS vessel traffic cells (~1.9M)
--   2. Cetacean sighting cells (some outside shipping lanes)
--
-- This ensures the mart-layer risk model can LEFT JOIN
-- both traffic and cetacean data without losing sightings
-- in whale-only areas.
--
-- Creates a PostGIS POINT geometry from the cell centroid
-- for downstream spatial joins (MPA overlay).

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

all_cells as (

    select * from ais_cells
    union
    select * from cetacean_cells

)

select
    h3_cell,
    cell_lat,
    cell_lon,
    ST_SetSRID(ST_MakePoint(cell_lon, cell_lat), 4326) as geom

from all_cells
