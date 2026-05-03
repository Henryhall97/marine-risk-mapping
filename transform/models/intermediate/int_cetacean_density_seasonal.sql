-- Intermediate model: cetacean sighting density per hex cell per season
-- Aggregates OBIS sighting records into seasonal summaries by
-- extracting the observation month from event_date.

{{ config(
    indexes=[
        {'columns': ['h3_cell', 'season']},
    ]
) }}

--
-- Only sightings with valid ISO dates (YYYY-MM-DD pattern) are
-- included — about 95% of records.
--
-- Grain: one row per (h3_cell, season).

with sighting_cells as (

    select
        m.h3_cell,
        s.scientific_name,
        s.species_label,
        s.taxonomic_level,
        s.taxonomic_family,
        s.observation_year,
        s.event_date,
        -- Extract month from ISO date string (first 10 chars → date)
        extract(month from left(s.event_date, 10)::date)::int as obs_month
    from {{ source('marine_risk', 'cetacean_sighting_h3') }} m
    inner join {{ ref('stg_cetacean_sightings') }} s
        on m.sighting_id = s.id
    -- Only records with parseable ISO dates
    where s.event_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'

),

with_season as (

    select
        *,
        {{ season_from_month('obs_month') }} as season
    from sighting_cells

),

cell_season_sightings as (

    select
        h3_cell,
        season,

        -- Total sighting count
        count(*)                              as total_sightings,
        count(distinct species_label)         as unique_species,

        -- Quality: how many are species-level IDs?
        count(*) filter (
            where taxonomic_level = 'species'
        )                                     as species_level_sightings,

        -- Recency: sightings in last 5 years
        count(*) filter (
            where observation_year >= {{ var('cetacean_recent_year') }}
        )                                     as recent_sightings,

        -- Baleen whales (highest collision risk)
        count(*) filter (
            where taxonomic_family in (
                'Balaenopteridae',
                'Balaenidae',
                'Eschrichtiidae'
            )
        )                                     as baleen_whale_sightings,

        -- ── Per-species counts (key strike-risk taxa) ──
        count(*) filter (
            where scientific_name = 'Eubalaena glacialis'
        )                                     as right_whale_sightings,
        count(*) filter (
            where scientific_name = 'Megaptera novaeangliae'
        )                                     as humpback_sightings,
        count(*) filter (
            where scientific_name = 'Balaenoptera physalus'
        )                                     as fin_whale_sightings,
        count(*) filter (
            where scientific_name = 'Balaenoptera musculus'
        )                                     as blue_whale_sightings,
        count(*) filter (
            where scientific_name = 'Physeter macrocephalus'
        )                                     as sperm_whale_sightings,
        count(*) filter (
            where scientific_name = 'Balaenoptera acutorostrata'
        )                                     as minke_whale_sightings,

        -- Temporal span
        min(observation_year)                 as earliest_year,
        max(observation_year)                 as latest_year

    from with_season
    where season is not null
    group by h3_cell, season

)

select * from cell_season_sightings
