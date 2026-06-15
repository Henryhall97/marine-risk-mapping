-- Mart: whale × vessel exposure (co-occurrence base layer)
--
-- IWC Phase 1 — "exposure-first" reporting (R. Leaper's explicit request):
-- report the RAW whale × vessel co-occurrence per cell as the BASE layer,
-- BEFORE any speed-lethality weighting is applied.  The speed-weighted
-- variant (Vanderlaan & Taggart lethality) is provided as an OPTIONAL
-- overlay so users can separate "where whales and ships overlap" from
-- "where overlap is most likely to be lethal".
--
-- Rationale: the collision-risk marts fold exposure and lethality into a
-- single composite.  Decoupling them makes the exposure signal — the
-- quantity most directly comparable across studies and least dependent on
-- modelling assumptions — visible on its own.
--
--   exposure_raw            = P(any whale) × vessel volume     (base layer)
--   exposure_speed_weighted = P(any whale) × speed lethality   (overlay)
--
-- Whale probability is the ISDM + SDM ensemble (same construction as
-- fct_collision_risk_ml): avg(ISDM, SDM) for the 4 shared species,
-- SDM-only for right whale and minke.
--
-- Grain: one row per (h3_cell, season). ~7.3M rows.

{{ config(
    indexes=[
        {'columns': ['h3_cell', 'season']},
        {'columns': ['exposure_score']},
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

features as (

    select
        gs.h3_cell,
        gs.cell_lat,
        gs.cell_lon,
        gs.geom,
        gs.season,

        -- ── Ensembled per-species P(present) (NULL-aware — item A) ──
        {{ ensemble_prob('ml.isdm_blue_whale', 'sdm.sdm_blue_whale', 'blue') }}
            as blue_whale_prob,
        {{ ensemble_prob('ml.isdm_fin_whale', 'sdm.sdm_fin_whale', 'fin') }}
            as fin_whale_prob,
        {{ ensemble_prob(
            'ml.isdm_humpback_whale', 'sdm.sdm_humpback_whale', 'humpback') }}
            as humpback_whale_prob,
        {{ ensemble_prob('ml.isdm_sperm_whale', 'sdm.sdm_sperm_whale', 'sperm') }}
            as sperm_whale_prob,
        coalesce(sdm.sdm_right_whale, 0) as right_whale_prob,
        coalesce(sdm.sdm_minke_whale, 0) as minke_whale_prob,
        coalesce(sdm.sdm_gray_whale, 0) as gray_whale_prob,
        coalesce(sdm.sdm_rices_whale, 0) as rices_whale_prob,

        -- ── Ensemble P(any whale) = 1 - ∏(1 - P_i) across 8 species ──
        -- NOTE (item F): assumes species independence and therefore
        -- over-estimates P(any whale); used here only as a rank index.
        1.0 - (
            (1.0 - {{ ensemble_prob(
                'ml.isdm_blue_whale', 'sdm.sdm_blue_whale', 'blue') }})
          * (1.0 - {{ ensemble_prob(
                'ml.isdm_fin_whale', 'sdm.sdm_fin_whale', 'fin') }})
          * (1.0 - {{ ensemble_prob(
                'ml.isdm_humpback_whale', 'sdm.sdm_humpback_whale', 'humpback') }})
          * (1.0 - {{ ensemble_prob(
                'ml.isdm_sperm_whale', 'sdm.sdm_sperm_whale', 'sperm') }})
          * (1.0 - coalesce(sdm.sdm_right_whale, 0))
          * (1.0 - coalesce(sdm.sdm_minke_whale, 0))
          * (1.0 - coalesce(sdm.sdm_gray_whale, 0))
          * (1.0 - coalesce(sdm.sdm_rices_whale, 0))
        ) as any_whale_prob,

        -- Mean bootstrap uncertainty across the two model families
        (coalesce(ml.mean_whale_sd, 0) + coalesce(sdm.mean_whale_sd, 0))
            / nullif(
                (case when ml.mean_whale_sd is not null then 1 else 0 end)
              + (case when sdm.mean_whale_sd is not null then 1 else 0 end),
                0
            ) as whale_prob_sd,
        coalesce(ml.isdm_extrapolated, false) as isdm_extrapolated,

        -- ── Vessel exposure inputs ──────────────────────
        -- Raw traffic volume (unweighted by speed) = the base-layer driver
        coalesce(t.avg_monthly_vessels, 0)  as vessel_volume,
        -- V&T speed-lethality (the overlay weighting)
        coalesce(t.avg_speed_lethality, 0)  as speed_lethality,

        t.h3_cell is not null as has_traffic,
        (ml.h3_cell is not null or sdm.h3_cell is not null)
            as has_ml_predictions

    from grid_seasons gs
    left join {{ ref('int_ml_whale_predictions') }} ml
        on gs.h3_cell = ml.h3_cell and gs.season = ml.season
    left join {{ ref('int_sdm_whale_predictions') }} sdm
        on gs.h3_cell = sdm.h3_cell and gs.season = sdm.season
    left join {{ ref('int_vessel_traffic_seasonal') }} t
        on gs.h3_cell = t.h3_cell and gs.season = t.season
    left join {{ ref('int_bathymetry') }} b
        on gs.h3_cell = b.h3_cell

    -- Ocean cells only (Natural Earth ocean mask)
    where coalesce(b.is_ocean, false) = true

),

exposure as (

    select
        *,
        -- Strike-weighted whale presence (item G): Σ Pᵢ × vulnᵢ
        {{ strike_weighted_exposure() }} as strike_weighted_presence,
        -- BASE layer: raw co-occurrence (no lethality weighting)
        any_whale_prob * vessel_volume          as exposure_raw,
        -- OPTIONAL overlay: lethality-weighted co-occurrence
        any_whale_prob * speed_lethality        as exposure_speed_weighted,
        -- OPTIONAL overlay: vulnerability-weighted co-occurrence
        {{ strike_weighted_exposure() }} * vessel_volume
            as exposure_strike_weighted
    from features

),

ranked as (

    select
        *,
        percent_rank() over (
            partition by season order by exposure_raw
        ) as exposure_score,
        percent_rank() over (
            partition by season order by exposure_speed_weighted
        ) as exposure_speed_score,
        percent_rank() over (
            partition by season order by exposure_strike_weighted
        ) as exposure_strike_score
    from exposure

)

select
    h3_cell,
    season,
    cell_lat,
    cell_lon,
    geom,

    round(any_whale_prob::numeric, 4)             as any_whale_prob,
    round(whale_prob_sd::numeric, 4)              as whale_prob_sd,
    round(strike_weighted_presence::numeric, 4)   as strike_weighted_presence,
    round(vessel_volume::numeric, 2)              as vessel_volume,
    round(speed_lethality::numeric, 4)            as speed_lethality,

    -- ── Base exposure layer (whale × vessel co-occurrence) ──
    round(exposure_raw::numeric, 4)               as exposure_raw,
    round(exposure_score::numeric, 4)             as exposure_score,

    -- ── Optional speed-lethality-weighted overlay ──────────
    round(exposure_speed_weighted::numeric, 4)    as exposure_speed_weighted,
    round(exposure_speed_score::numeric, 4)       as exposure_speed_score,

    -- ── Optional vulnerability-weighted overlay (item G) ───
    round(exposure_strike_weighted::numeric, 4)   as exposure_strike_weighted,
    round(exposure_strike_score::numeric, 4)      as exposure_strike_score,

    isdm_extrapolated,
    has_traffic,
    has_ml_predictions

from ranked
