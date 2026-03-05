-- Mart model: seasonal whale species distribution model (SDM) training set
--
-- Same feature set as fct_whale_sdm_training but at (h3_cell, season) grain.
-- The target variable (whale_present) now varies by season, reflecting
-- the real-world seasonality of whale distribution patterns.
--
-- Key differences from fct_whale_sdm_training:
--   1. Grain is (h3_cell, season) → ~7.2M rows vs 1.8M
--   2. Cetacean sightings are seasonal (int_cetacean_density_seasonal)
--   3. Speed zone coverage is seasonal (int_speed_zone_coverage_seasonal)
--   4. Traffic features EXCLUDED (detection bias — survey effort
--      correlates with traffic density, biasing whale_present target)
--   5. Ocean covariates are seasonal (climatological means per season)
--
-- Designed for training seasonal SDMs with XGBoost/LightGBM.
-- Cross-validation should use spatial blocks (H3 res-2 parent cells).

{{ config(
    indexes=[
        {'columns': ['h3_cell', 'season']},
        {'columns': ['geom'], 'type': 'gist'},
    ]
) }}

with seasons as (

    select unnest(array['winter', 'spring', 'summer', 'fall']) as season

),

grid_seasons as (

    select
        g.h3_cell,
        g.cell_lat,
        g.cell_lon,
        g.geom,
        s.season
    from {{ ref('int_hex_grid') }} g
    cross join seasons s

),

base as (

    select
        gs.h3_cell,
        gs.season,
        gs.cell_lat,
        gs.cell_lon,
        gs.geom,

        -- ── Target variable (seasonal) ───────────────
        case when c.h3_cell is not null then 1 else 0 end
            as whale_present,

        -- Richer targets for multi-class or regression
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

        -- ── Ocean environment (seasonal) ─────────────
        oc.sst,
        oc.sst_sd,
        oc.mld,
        oc.sla,
        oc.pp_upper_200m,
        oc.covariate_dist_km,

        -- ── Bathymetry (static) ──────────────────────
        b.depth_m,
        b.depth_range_m,
        coalesce(b.is_continental_shelf, false)    as is_continental_shelf,
        coalesce(b.is_shelf_edge, false)           as is_shelf_edge,
        b.depth_zone,

        -- ── Nisi reference risk (static) ─────────────
        nr.nisi_all_risk,
        nr.nisi_shipping_index,
        nr.nisi_whale_space_use,
        coalesce(nr.nisi_hotspot_overlap, 0)        as nisi_hotspot_overlap,
        nr.nisi_dist_km,
        -- Per-species Nisi risk (validation benchmarks)
        nr.nisi_blue_risk,
        nr.nisi_fin_risk,
        nr.nisi_humpback_risk,
        nr.nisi_sperm_risk,

        -- ── Proximity (static) ───────────────────────
        -- NOTE: whale_proximity_score excluded from SDM
        -- (encodes the target → leakage)
        p.dist_to_nearest_ship_km,
        p.ship_proximity_score,
        p.dist_to_nearest_strike_km,
        p.strike_proximity_score,
        p.dist_to_nearest_protection_km,
        p.protection_proximity_score,

        -- ── Speed zone context (seasonal) ────────────
        coalesce(sz.in_speed_zone, false)          as in_speed_zone,
        coalesce(sz.in_current_sma, false)         as in_current_sma,

        -- ── MPA context (static) ─────────────────────
        coalesce(m.mpa_count, 0)                   as mpa_count,
        coalesce(m.has_strict_protection, false)   as has_strict_protection,

        -- ── Exclude non-ocean ────────────────────────
        coalesce(b.is_ocean, false)                 as is_ocean

    from grid_seasons gs
    left join {{ ref('int_cetacean_density_seasonal') }} c
        on gs.h3_cell = c.h3_cell and gs.season = c.season
    left join {{ ref('int_ocean_covariates_seasonal') }} oc
        on gs.h3_cell = oc.h3_cell and gs.season = oc.season
    left join {{ ref('int_bathymetry') }} b
        on gs.h3_cell = b.h3_cell
    left join {{ ref('int_nisi_reference_risk') }} nr
        on gs.h3_cell = nr.h3_cell
    left join {{ ref('int_proximity') }} p
        on gs.h3_cell = p.h3_cell
    left join {{ ref('int_speed_zone_coverage_seasonal') }} sz
        on gs.h3_cell = sz.h3_cell and gs.season = sz.season
    left join {{ ref('int_mpa_coverage') }} m
        on gs.h3_cell = m.h3_cell

)

select
    h3_cell,
    season,
    cell_lat,
    cell_lon,
    geom,
    whale_present,
    total_sightings,
    unique_species,
    baleen_whale_sightings,
    recent_sightings,
    right_whale_present,
    humpback_present,
    fin_whale_present,
    blue_whale_present,
    sperm_whale_present,
    minke_whale_present,
    sst,
    sst_sd,
    mld,
    sla,
    pp_upper_200m,
    covariate_dist_km,
    depth_m,
    depth_range_m,
    is_continental_shelf,
    is_shelf_edge,
    depth_zone,
    nisi_all_risk,
    nisi_shipping_index,
    nisi_whale_space_use,
    nisi_hotspot_overlap,
    nisi_dist_km,
    nisi_blue_risk,
    nisi_fin_risk,
    nisi_humpback_risk,
    nisi_sperm_risk,
    dist_to_nearest_ship_km,
    ship_proximity_score,
    dist_to_nearest_strike_km,
    strike_proximity_score,
    dist_to_nearest_protection_km,
    protection_proximity_score,
    in_speed_zone,
    in_current_sma,
    mpa_count,
    has_strict_protection

from base
where is_ocean
