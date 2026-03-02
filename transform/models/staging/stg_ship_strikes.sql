-- Staging model: ship strikes
-- Cleans and standardises the raw NOAA ship strike records.
--
-- What this does:
--   1. Selects key columns for downstream models
--   2. Joins the species_crosswalk seed for consistent species
--      identification across OBIS sightings, Nisi ISDM, and strikes
--   3. Classifies outcome severity from free-text mortality_injury
--   4. Flags whether the strike has coordinates
--
-- The crosswalk maps strike common names (right, finback, humpback)
-- to the same species_group identifiers used in cetacean sightings,
-- enabling direct comparison between where whales are seen and
-- where they get struck.

with source as (

    select * from {{ source('marine_risk', 'ship_strikes') }}

),

-- The crosswalk has one row per scientific_name, but strikes use
-- common names. We need a distinct mapping from strike_species
-- to species_group. Take the first match (all should be identical
-- for a given strike_species value).
strike_xw as (

    select distinct on (strike_species)
        strike_species,
        species_group,
        common_name,
        is_baleen,
        conservation_priority,
        nisi_species
    from {{ ref('species_crosswalk') }}
    where strike_species is not null
      and strike_species != ''
    order by strike_species, taxonomic_rank  -- prefer species-rank rows

),

cleaned as (

    select
        s.id,
        s.incident_date,
        s.species              as species_raw,
        coalesce(xw.species_group, 'unknown')   as species_group,
        coalesce(xw.common_name, s.species)      as common_name,
        coalesce(xw.is_baleen, false)            as is_baleen,
        coalesce(xw.conservation_priority, 'unknown') as conservation_priority,
        xw.nisi_species,
        s.sex,
        s.length_m,
        s.location_desc,
        s.latitude,
        s.longitude,
        s.region,
        s.mortality_injury,

        -- Outcome severity
        case
            when s.mortality_injury ilike '%mortality%'
              or s.mortality_injury ilike '%dead%'
              or s.mortality_injury ilike '%lethal%'       then 'fatal'
            when s.mortality_injury ilike '%serious%'      then 'serious_injury'
            when s.mortality_injury ilike '%injury%'       then 'injury'
            else 'unknown'
        end as outcome_severity,

        -- Has coordinates?
        (s.latitude is not null and s.longitude is not null) as is_geocoded,

        s.geom

    from source s
    left join strike_xw xw
        on s.species = xw.strike_species

)

select * from cleaned
