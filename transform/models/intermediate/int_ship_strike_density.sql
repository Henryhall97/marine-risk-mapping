-- Intermediate model: ship strike density per hex cell
-- Aggregates geocoded ship strikes to H3 resolution-7 cells
-- using the pre-computed ship_strike_h3 mapping.
--
-- Joins back to stg_ship_strikes for species/outcome detail.
-- Only the 67 geocoded strikes contribute; the remaining 194
-- are captured in overall counts but not in spatial density.
--
-- Grain: one row per h3_cell.

with strike_cells as (

    select
        m.h3_cell,
        m.cell_lat,
        m.cell_lon,
        s.species_raw,
        s.species_group,
        s.is_baleen,
        s.outcome_severity,
        s.incident_date
    from {{ source('marine_risk', 'ship_strike_h3') }} m
    inner join {{ ref('stg_ship_strikes') }} s
        on m.strike_id = s.id

),

cell_strikes as (

    select
        h3_cell,

        -- Total strikes in this cell
        count(*)                              as total_strikes,

        -- Fatal strikes
        count(*) filter (
            where outcome_severity = 'fatal'
        )                                     as fatal_strikes,

        -- Serious injury
        count(*) filter (
            where outcome_severity = 'serious_injury'
        )                                     as serious_injury_strikes,

        -- Baleen whale strikes (highest conservation concern)
        count(*) filter (
            where is_baleen
        )                                     as baleen_strikes,

        -- Right whale strikes (critically endangered)
        count(*) filter (
            where species_group = 'right_whale'
        )                                     as right_whale_strikes,

        -- Species diversity
        count(distinct species_group)         as unique_species_groups,

        -- String list of species hit (for debugging/labels)
        string_agg(distinct species_group, '; ' order by species_group)
                                              as species_list

    from strike_cells
    group by h3_cell

)

select * from cell_strikes
