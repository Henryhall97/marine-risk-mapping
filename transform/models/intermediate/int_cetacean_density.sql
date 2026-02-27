-- Intermediate model: cetacean sighting density per hex cell
-- Uses pre-computed H3 cell assignments from the Python h3
-- library (pipeline/aggregation/assign_cetacean_h3.py) rather
-- than expensive PostGIS spatial joins.
--
-- Each sighting gets an exact H3 cell via h3.latlng_to_cell(),
-- so cells are correct even when no vessel traffic exists nearby.
-- The mart layer LEFT JOINs this with vessel traffic to produce
-- risk scores — cells with whales but no ships get null traffic.
--
-- Grain: one row per h3_cell (time-aggregated).

with sighting_cells as (

    select
        m.h3_cell,
        s.species_label,
        s.taxonomic_level,
        s.taxonomic_family,
        s.observation_year
    from {{ source('marine_risk', 'cetacean_sighting_h3') }} m
    inner join {{ ref('stg_cetacean_sightings') }} s
        on m.sighting_id = s.id

),

cell_sightings as (

    select
        h3_cell,

        -- Total sighting count
        count(*)                              as total_sightings,
        count(distinct species_label)         as unique_species,

        -- Quality: how many are species-level IDs?
        count(*) filter (
            where taxonomic_level = 'species'
        )                                     as species_level_sightings,

        -- Recency: sightings in last 5 years
        count(*) filter (
            where observation_year >= 2019
        )                                     as recent_sightings,

        -- Baleen whales (highest collision risk)
        -- Balaenopteridae = rorquals (blue, fin, humpback, minke)
        -- Balaenidae = right whales (North Atlantic right whale)
        -- Eschrichtiidae = gray whale
        count(*) filter (
            where taxonomic_family in (
                'Balaenopteridae',
                'Balaenidae',
                'Eschrichtiidae'
            )
        )                                     as baleen_whale_sightings,

        -- Temporal span
        min(observation_year)                 as earliest_year,
        max(observation_year)                 as latest_year

    from sighting_cells
    group by h3_cell

)

select * from cell_sightings
