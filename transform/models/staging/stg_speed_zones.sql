-- Staging model: speed zones (both proposed and current SMAs)
-- Unions the proposed speed zones and current active SMAs into
-- a single clean layer for downstream spatial joins.
--
-- What this does:
--   1. Reads both speed zone sources
--   2. Normalises column names across both
--   3. Adds a source_type flag (proposed vs current_sma)
--   4. Computes season dates as month-day strings for readability

with proposed as (

    select
        id,
        zone_name,
        null::varchar(10)  as zone_abbr,
        start_month,
        start_day,
        end_month,
        end_day,
        area_sq_deg,
        perimeter_deg,
        'proposed'         as source_type,
        geom
    from {{ source('marine_risk', 'right_whale_speed_zones') }}

),

current_sma as (

    select
        id,
        zone_name,
        zone_abbr,
        start_month,
        start_day,
        end_month,
        end_day,
        area_sq_deg,
        perimeter_deg,
        'current_sma'      as source_type,
        geom
    from {{ source('marine_risk', 'seasonal_management_areas') }}

),

combined as (

    select * from proposed
    union all
    select * from current_sma

),

cleaned as (

    select
        id,
        zone_name,
        zone_abbr,
        source_type,
        start_month,
        start_day,
        end_month,
        end_day,
        area_sq_deg,
        perimeter_deg,

        -- Readable season string (e.g. "Nov 1 – Apr 30")
        to_char(make_date(2000, start_month, start_day), 'Mon DD')
            || ' – '
            || to_char(make_date(2000, end_month, end_day), 'Mon DD')
            as season_label,

        -- Season length in days (approximate — ignoring year wrap)
        case
            when make_date(2000, end_month, end_day)
                 >= make_date(2000, start_month, start_day)
            then make_date(2000, end_month, end_day)
                 - make_date(2000, start_month, start_day)
            else (make_date(2001, end_month, end_day)
                  - make_date(2000, start_month, start_day))
        end as season_days,

        -- Fix any invalid geometries
        ST_MakeValid(geom) as geom

    from combined

)

select * from cleaned
