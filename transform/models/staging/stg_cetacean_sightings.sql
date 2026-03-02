-- Staging model: cetacean sightings
-- Cleans and standardises the raw OBIS whale sighting data.
--
-- What this does:
--   1. Selects only the columns we need downstream
--   2. Normalises 'NaN' string values to NULL
--   3. Backfills species_label from scientific_name when species is null
--   4. Casts date_year from float to integer
--   5. Classifies taxonomic precision (species/genus/family/higher)
--   6. Derives is_baleen from taxonomic family
--
-- Taxonomic precision note:
--   ~11% of records have species='NaN' and are only identified to
--   genus (e.g. Balaenoptera), family (e.g. Delphinidae), or order
--   (e.g. Cetacea). These are valuable for density estimation but
--   should not be used for species-specific analysis.

with source as (

    select * from {{ source('marine_risk', 'cetacean_sightings') }}

),

normalised as (

    -- Treat 'NaN' strings (from pandas) as NULL
    select
        id,
        scientific_name,
        decimal_latitude,
        decimal_longitude,
        event_date,
        date_year,
        "order",
        nullif(family, 'NaN')   as family_clean,
        nullif(species, 'NaN')  as species_clean,
        geom
    from source

),

cleaned as (

    select
        id,
        scientific_name,
        decimal_latitude   as latitude,
        decimal_longitude  as longitude,
        event_date,
        date_year::integer as observation_year,

        -- Best available name: species if identified, else scientific_name
        -- (scientific_name is always populated — may be genus or family)
        coalesce(species_clean, scientific_name) as species_label,

        -- Taxonomic precision based on actual identification level.
        -- A binomial scientific_name (two words) = species-level ID.
        -- Single word = genus or higher.
        case
            when species_clean is not null
                then 'species'
            when family_clean is not null
                 and array_length(string_to_array(scientific_name, ' '), 1) = 1
                then 'genus'
            when family_clean is not null
                then 'family'
            else 'higher'
        end as taxonomic_level,

        "order"        as taxonomic_order,
        family_clean   as taxonomic_family,
        species_clean  as species_raw,

        -- Baleen whale flag from taxonomic family
        -- Balaenopteridae = rorquals (blue, fin, humpback, sei, minke, Bryde's)
        -- Balaenidae = right whales, bowhead
        -- Eschrichtiidae = gray whale
        coalesce(family_clean, '') in (
            'Balaenopteridae', 'Balaenidae', 'Eschrichtiidae'
        ) as is_baleen,

        geom

    from normalised

)

select * from cleaned
