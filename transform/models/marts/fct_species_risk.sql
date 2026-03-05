-- Mart model: species-level risk assessment
--
-- Breaks down collision risk by cetacean species group.
-- Each row represents a species × H3 cell combination where
-- that species has been sighted.
--
-- Uses the species_crosswalk seed for consistent species
-- identification across OBIS sightings, Nisi ISDM, and
-- ship strike data. Only species-level identifications are
-- included to avoid inflating counts with genus/family records.
-- (~11% of sightings are sub-species precision — these still
-- contribute to int_cetacean_density total counts.)
--
-- Useful for:
--   - Species-specific risk maps (e.g. right whale vs humpback)
--   - Conservation priority ranking
--   - ESA Section 7 consultation support
--   - Comparing species exposure to different threat types
--   - Validation against Nisi ISDM (4 overlapping species)
--
-- Grain: one row per (h3_cell, species_group).

{{ config(
    indexes=[
        {'columns': ['h3_cell']},
        {'columns': ['species_group']},
        {'columns': ['geom'], 'type': 'gist'},
    ]
) }}

with species_cells as (

    -- Join sightings → crosswalk for canonical species_group.
    -- The crosswalk maps scientific_name to a consistent group
    -- across OBIS, Nisi ISDM, and ship strike datasets.
    select
        ch.h3_cell,
        s.species_label                       as species,
        s.scientific_name,
        xw.species_group,
        xw.common_name,
        xw.nisi_species,
        xw.is_baleen,
        xw.conservation_priority,
        s.taxonomic_level,
        count(*)                              as sighting_count,
        min(s.observation_year)               as earliest_year,
        max(s.observation_year)               as latest_year

    from {{ source('marine_risk', 'cetacean_sighting_h3') }} ch
    inner join {{ ref('stg_cetacean_sightings') }} s
        on ch.sighting_id = s.id
    inner join {{ ref('species_crosswalk') }} xw
        on s.scientific_name = xw.scientific_name
    -- Only species-level identifications for species-specific analysis
    where s.taxonomic_level = 'species'
    group by ch.h3_cell, s.species_label, s.scientific_name,
             xw.species_group, xw.common_name, xw.nisi_species,
             xw.is_baleen, xw.conservation_priority, s.taxonomic_level

),

enriched as (

    select
        sc.h3_cell,
        sc.species,
        sc.common_name,
        sc.species_group,
        sc.is_baleen,
        sc.conservation_priority,
        sc.nisi_species,
        sc.sighting_count,
        sc.earliest_year,
        sc.latest_year,

        -- Grid context
        g.cell_lat,
        g.cell_lon,
        g.geom,

        -- Traffic exposure
        t.avg_monthly_vessels,
        t.avg_speed_knots,
        t.peak_speed_knots,
        t.avg_high_speed_vessels,
        t.avg_large_vessels,
        t.avg_commercial_vessels,

        -- Strike history for this cell (all species)
        coalesce(ss.total_strikes, 0)         as cell_total_strikes,
        coalesce(ss.fatal_strikes, 0)         as cell_fatal_strikes,

        -- Speed zone protection
        coalesce(sz.in_speed_zone, false)     as in_speed_zone,
        coalesce(sz.in_current_sma, false)    as in_current_sma,

        -- MPA protection
        coalesce(m.mpa_count, 0)              as mpa_count,
        coalesce(m.has_strict_protection, false) as has_strict_protection,

        -- Bathymetry
        b.depth_m,
        b.depth_zone,

        -- Ocean environment
        oc.sst,
        oc.mld,
        oc.pp_upper_200m,

        -- Nisi reference (species-specific where available via crosswalk)
        nr.nisi_all_risk,
        case sc.nisi_species
            when 'Blue'    then nr.nisi_blue_risk
            when 'Fin'     then nr.nisi_fin_risk
            when 'Humpback' then nr.nisi_humpback_risk
            when 'Sperm'   then nr.nisi_sperm_risk
            else null
        end as nisi_species_risk,

        -- Ocean mask flag for filtering
        coalesce(b.is_ocean, false)           as is_ocean

    from species_cells sc
    inner join {{ ref('int_hex_grid') }} g
        on sc.h3_cell = g.h3_cell
    left join (
        select
            h3_cell,
            avg(unique_vessels)           as avg_monthly_vessels,
            avg(vw_avg_speed_knots)       as avg_speed_knots,
            max(max_speed_knots)          as peak_speed_knots,
            avg(high_speed_vessel_count)  as avg_high_speed_vessels,
            avg(large_vessel_count)       as avg_large_vessels,
            avg(cargo_vessels + tanker_vessels) as avg_commercial_vessels
        from {{ ref('int_vessel_traffic') }}
        group by h3_cell
    ) t on sc.h3_cell = t.h3_cell
    left join {{ ref('int_ship_strike_density') }} ss
        on sc.h3_cell = ss.h3_cell
    left join {{ ref('int_speed_zone_coverage') }} sz
        on sc.h3_cell = sz.h3_cell
    left join {{ ref('int_mpa_coverage') }} m
        on sc.h3_cell = m.h3_cell
    left join {{ ref('int_bathymetry') }} b
        on sc.h3_cell = b.h3_cell
    left join {{ ref('int_ocean_covariates') }} oc
        on sc.h3_cell = oc.h3_cell
    left join {{ ref('int_nisi_reference_risk') }} nr
        on sc.h3_cell = nr.h3_cell

)

select
    h3_cell,
    cell_lat,
    cell_lon,
    geom,
    species,
    common_name,
    species_group,
    is_baleen,
    conservation_priority,
    nisi_species,
    sighting_count,
    earliest_year,
    latest_year,

    -- Exposure metrics
    avg_monthly_vessels,
    avg_speed_knots,
    peak_speed_knots,
    avg_high_speed_vessels,
    avg_large_vessels,
    avg_commercial_vessels,

    -- Strike history
    cell_total_strikes,
    cell_fatal_strikes,

    -- Protection
    in_speed_zone,
    in_current_sma,
    mpa_count,
    has_strict_protection,

    -- Habitat
    depth_m,
    depth_zone,
    sst,
    mld,
    pp_upper_200m,

    -- Reference benchmarks
    nisi_all_risk,
    nisi_species_risk,

    -- Simple species-level risk indicator
    -- High = lots of sightings, lots of traffic, no protection
    round((
        0.30 * (sighting_count::float / nullif(max(sighting_count) over (partition by species_group), 0))
      + 0.30 * (coalesce(avg_monthly_vessels, 0)::float / nullif(max(avg_monthly_vessels) over (), 0))
      + 0.20 * (coalesce(avg_high_speed_vessels, 0)::float / nullif(max(avg_high_speed_vessels) over (), 0))
      + 0.20 * case
                  when in_current_sma then 0.2
                  when in_speed_zone  then 0.4
                  when mpa_count > 0  then 0.6
                  else 1.0
               end
    )::numeric, 4) as species_risk_score

from enriched
-- Exclude non-ocean cells (Natural Earth ocean mask)
where is_ocean
