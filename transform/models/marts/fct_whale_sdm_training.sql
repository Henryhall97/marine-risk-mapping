-- Mart model: whale species distribution model (SDM) training set
--
-- One row per H3 cell with a binary presence/absence target
-- for cetacean sightings, plus all environmental and spatial
-- features needed to train an SDM.
--
-- Target variable:
--   whale_present (1/0) — has this cell ever had a cetacean sighting?
--
-- Feature groups:
--   - Ocean covariates (SST, MLD, SLA, PP)
--   - Bathymetry (depth, shelf, slope)
--   - Spatial (lat/lon)
--   - Nisi reference risk (external benchmark)
--   - Proximity (distance to shipping, other sighting cells)
--
-- Designed for binary classifiers (logistic regression, random
-- forest, XGBoost) or MaxEnt-style presence-only models.
--
-- Grain: one row per h3_cell.

{{ config(
    indexes=[
        {'columns': ['h3_cell']},
        {'columns': ['geom'], 'type': 'gist'},
    ]
) }}

with base as (

    select
        g.h3_cell,
        g.cell_lat,
        g.cell_lon,
        g.geom,

        -- ── Target variable ──────────────────────────
        case when c.h3_cell is not null then 1 else 0 end
            as whale_present,

        -- Richer target variants for multi-class or regression
        coalesce(c.total_sightings, 0)            as total_sightings,
        coalesce(c.unique_species, 0)              as unique_species,
        coalesce(c.baleen_whale_sightings, 0)      as baleen_whale_sightings,
        coalesce(c.recent_sightings, 0)            as recent_sightings,

        -- Per-species presence (alternative binary targets)
        case when coalesce(c.right_whale_sightings, 0) > 0 then 1 else 0 end
            as right_whale_present,
        case when coalesce(c.humpback_sightings, 0) > 0 then 1 else 0 end
            as humpback_present,
        case when coalesce(c.fin_whale_sightings, 0) > 0 then 1 else 0 end
            as fin_whale_present,
        case when coalesce(c.blue_whale_sightings, 0) > 0 then 1 else 0 end
            as blue_whale_present,
        case when coalesce(c.sperm_whale_sightings, 0) > 0 then 1 else 0 end
            as sperm_whale_present,
        case when coalesce(c.minke_whale_sightings, 0) > 0 then 1 else 0 end
            as minke_whale_present,

        -- ── Ocean environment features ───────────────
        oc.sst,
        oc.sst_sd,
        oc.mld,
        oc.sla,
        oc.pp_upper_200m,
        oc.covariate_dist_km,

        -- ── Bathymetry features ──────────────────────
        b.depth_m,
        b.depth_range_m,
        coalesce(b.is_continental_shelf, false)    as is_continental_shelf,
        coalesce(b.is_shelf_edge, false)           as is_shelf_edge,
        b.depth_zone,

        -- ── Nisi reference risk (external benchmark) ─
        nr.nisi_all_risk,
        nr.nisi_shipping_index,
        nr.nisi_whale_space_use,
        coalesce(nr.nisi_hotspot_overlap, 0)        as nisi_hotspot_overlap,
        nr.nisi_dist_km,

        -- ── Proximity features ───────────────────────
        p.dist_to_nearest_whale_km,
        p.dist_to_nearest_ship_km,
        p.whale_proximity_score,
        p.ship_proximity_score,
        p.dist_to_nearest_strike_km,
        p.strike_proximity_score,
        p.dist_to_nearest_protection_km,
        p.protection_proximity_score,

        -- ── Speed zone context ───────────────────────
        coalesce(sz.in_speed_zone, false)          as in_speed_zone,
        coalesce(sz.in_current_sma, false)         as in_current_sma,

        -- ── MPA context ──────────────────────────────
        coalesce(m.mpa_count, 0)                   as mpa_count,
        coalesce(m.has_strict_protection, false)   as has_strict_protection,

        -- ── Traffic context (predictor, not target) ──
        t.avg_monthly_vessels,
        t.avg_speed_knots,
        t.months_active,

        -- ── Exclude non-ocean ────────────────────────
        coalesce(b.is_ocean, false)                 as is_ocean

    from {{ ref('int_hex_grid') }} g
    left join {{ ref('int_cetacean_density') }} c
        on g.h3_cell = c.h3_cell
    left join {{ ref('int_ocean_covariates') }} oc
        on g.h3_cell = oc.h3_cell
    left join {{ ref('int_bathymetry') }} b
        on g.h3_cell = b.h3_cell
    left join {{ ref('int_nisi_reference_risk') }} nr
        on g.h3_cell = nr.h3_cell
    left join {{ ref('int_proximity') }} p
        on g.h3_cell = p.h3_cell
    left join {{ ref('int_speed_zone_coverage') }} sz
        on g.h3_cell = sz.h3_cell
    left join {{ ref('int_mpa_coverage') }} m
        on g.h3_cell = m.h3_cell
    left join (
        select
            h3_cell,
            avg(unique_vessels)   as avg_monthly_vessels,
            avg(vw_avg_speed_knots) as avg_speed_knots,
            count(distinct month) as months_active
        from {{ ref('int_vessel_traffic') }}
        group by h3_cell
    ) t
        on g.h3_cell = t.h3_cell

)

select * from base
where is_ocean
