-- Staging model: cetacean sightings
-- Cleans and standardises the raw OBIS whale sighting data.
--
-- What this does:
--   1. Selects only the columns we need downstream
--   2. Backfills species from scientific_name when null
--   3. Casts date_year from float to integer
--   4. Adds a readable label for taxonomic precision

with source as (

    select * from {{ source('marine_risk', 'cetacean_sightings') }}

),

cleaned as (

    select
        id,
        scientific_name,
        decimal_latitude   as latitude,
        decimal_longitude  as longitude,
        event_date,
        date_year::integer as observation_year,

        -- Backfill: if species is null, use scientific_name
        -- (these are genus/family-level IDs, still useful)
        coalesce(species, scientific_name) as species_label,

        -- Flag the taxonomic precision so we can filter later
        case
            when species is not null then 'species'
            when family is not null  then 'family'
            else 'higher'
        end as taxonomic_level,

        "order"  as taxonomic_order,
        family   as taxonomic_family,
        species  as species_raw,
        geom

    from source

)

select * from cleaned
