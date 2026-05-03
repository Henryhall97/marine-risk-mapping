-- Mart: Climate-projected ML-enhanced whale–vessel collision risk
--
-- Projects the ML-enhanced collision risk score into future decades
-- under CMIP6 climate scenarios (SSP2-4.5, SSP5-8.5; 2030s–2080s).
--
-- Architecture:
--   Builds on fct_collision_risk_ml — reuses 4 STATIC sub-scores
--   (traffic, strike, protection_gap, reference) that do not depend
--   on whale habitat.  The 2 whale-dependent sub-scores (interaction
--   + whale_ml) are recomputed from projected whale probabilities.
--
--   Proximity sub-score is REMOVED from projections (15% → 0%,
--   remaining 6 sub-scores renormalized to sum 1.0).  Rationale:
--   the proximity blend's whale-proximity component (6.75% of total)
--   measures distance to *current* sightings, which is meaningless
--   under future habitat shifts.  Removing the entire proximity
--   sub-score is cleaner than selectively zeroing one component.
--
--   Whale predictions are an ENSEMBLE of ISDM + SDM:
--   - For 4 shared species (blue, fin, humpback, sperm): average
--     of ISDM and SDM predictions, reducing model-specific bias.
--   - For 2 SDM-only species (right whale, minke): SDM prediction.
--   - Composites (any_whale_prob, max, mean) computed from all 6
--     ensembled species — giving right whale coverage that the
--     ISDM alone lacks.
--
-- Why build on fct_collision_risk_ml rather than re-joining 13
-- intermediate tables:
--   1. Static sub-scores are IDENTICAL regardless of whale data.
--   2. Avoids redundant joins to 10+ intermediate tables.
--   3. Keeps the projected mart lean and fast to rebuild.
--   4. Clear dependency: current risk must exist before projections.
--
-- Percentile ranking: PARTITION BY (scenario, decade, season).
--   Each projection gets its own ranking universe so that risk scores
--   are relative within a scenario/decade.
--
-- Grain: one row per (h3_cell, season, scenario, decade). ~58M rows.
--         (1.8M cells × 4 seasons × 2 scenarios × 4 decades)

{{ config(
    materialized='table',
    indexes=[
        {'columns': ['h3_cell', 'season', 'scenario', 'decade']},
        {'columns': ['cell_lat', 'cell_lon']},
        {'columns': ['scenario', 'decade', 'season']},
        {'columns': ['risk_score']},
    ]
) }}

with projected_whale as (

    -- Ensemble ISDM + SDM projected whale probabilities.
    -- 4 shared species: avg(ISDM, SDM) to reduce model-specific bias.
    -- 2 SDM-only species (right, minke): SDM value directly.
    -- Composites computed from all 6 ensembled per-species values.
    select
        isdm.h3_cell,
        isdm.season,
        isdm.scenario,
        isdm.decade,

        -- Raw model predictions (retained for diagnostics)
        isdm.isdm_blue_whale,
        isdm.isdm_fin_whale,
        isdm.isdm_humpback_whale,
        isdm.isdm_sperm_whale,
        sdm.sdm_right_whale,
        sdm.sdm_minke_whale,

        -- Ensembled per-species: avg of both models for shared species
        (coalesce(isdm.isdm_blue_whale, 0)
            + coalesce(sdm.sdm_blue_whale, 0)) / 2.0
            as blue_whale_prob,
        (coalesce(isdm.isdm_fin_whale, 0)
            + coalesce(sdm.sdm_fin_whale, 0)) / 2.0
            as fin_whale_prob,
        (coalesce(isdm.isdm_humpback_whale, 0)
            + coalesce(sdm.sdm_humpback_whale, 0)) / 2.0
            as humpback_whale_prob,
        (coalesce(isdm.isdm_sperm_whale, 0)
            + coalesce(sdm.sdm_sperm_whale, 0)) / 2.0
            as sperm_whale_prob,
        -- SDM-only species (no ISDM counterpart)
        coalesce(sdm.sdm_right_whale, 0) as right_whale_prob,
        coalesce(sdm.sdm_minke_whale, 0) as minke_whale_prob,

        -- Composite: maximum across all 6 ensembled species
        greatest(
            (coalesce(isdm.isdm_blue_whale, 0)
                + coalesce(sdm.sdm_blue_whale, 0)) / 2.0,
            (coalesce(isdm.isdm_fin_whale, 0)
                + coalesce(sdm.sdm_fin_whale, 0)) / 2.0,
            (coalesce(isdm.isdm_humpback_whale, 0)
                + coalesce(sdm.sdm_humpback_whale, 0)) / 2.0,
            (coalesce(isdm.isdm_sperm_whale, 0)
                + coalesce(sdm.sdm_sperm_whale, 0)) / 2.0,
            coalesce(sdm.sdm_right_whale, 0),
            coalesce(sdm.sdm_minke_whale, 0)
        ) as max_whale_prob,

        -- Composite: mean across all 6 ensembled species
        (
            (coalesce(isdm.isdm_blue_whale, 0)
                + coalesce(sdm.sdm_blue_whale, 0)) / 2.0
          + (coalesce(isdm.isdm_fin_whale, 0)
                + coalesce(sdm.sdm_fin_whale, 0)) / 2.0
          + (coalesce(isdm.isdm_humpback_whale, 0)
                + coalesce(sdm.sdm_humpback_whale, 0)) / 2.0
          + (coalesce(isdm.isdm_sperm_whale, 0)
                + coalesce(sdm.sdm_sperm_whale, 0)) / 2.0
          + coalesce(sdm.sdm_right_whale, 0)
          + coalesce(sdm.sdm_minke_whale, 0)
        ) / 6.0 as mean_whale_prob,

        -- Composite: P(any whale) = 1 - ∏(1 - P_i) across 6 species
        1.0 - (
            (1.0 - (coalesce(isdm.isdm_blue_whale, 0)
                + coalesce(sdm.sdm_blue_whale, 0)) / 2.0)
          * (1.0 - (coalesce(isdm.isdm_fin_whale, 0)
                + coalesce(sdm.sdm_fin_whale, 0)) / 2.0)
          * (1.0 - (coalesce(isdm.isdm_humpback_whale, 0)
                + coalesce(sdm.sdm_humpback_whale, 0)) / 2.0)
          * (1.0 - (coalesce(isdm.isdm_sperm_whale, 0)
                + coalesce(sdm.sdm_sperm_whale, 0)) / 2.0)
          * (1.0 - coalesce(sdm.sdm_right_whale, 0))
          * (1.0 - coalesce(sdm.sdm_minke_whale, 0))
        ) as any_whale_prob

    from {{ source('marine_risk', 'whale_isdm_projections') }} isdm
    inner join {{ source('marine_risk', 'whale_sdm_projections') }} sdm
        on  isdm.h3_cell  = sdm.h3_cell
        and isdm.season   = sdm.season
        and isdm.scenario = sdm.scenario
        and isdm.decade   = sdm.decade

),

-- Grab the current (static) sub-scores that don't change with projections.
-- These are already final 0–1 percentile-ranked values.
-- NOTE: proximity_score deliberately excluded — see header comment.
current_static as (

    select
        h3_cell,
        season,
        cell_lat,
        cell_lon,
        geom,

        -- 4 static sub-scores (unchanged under climate projections)
        traffic_score,
        strike_score,
        protection_gap,
        reference_risk_score,

        -- Feature flags
        has_traffic,
        in_mpa,
        has_strike_history,
        in_speed_zone,
        in_current_sma,
        in_proposed_zone,
        has_nisi_reference

    from {{ ref('fct_collision_risk_ml') }}

),

-- Join projected whale probs with current static sub-scores.
-- Compute raw whale × traffic interaction for subsequent ranking.
joined as (

    select
        pw.h3_cell,
        pw.season,
        pw.scenario,
        pw.decade,

        -- Projected whale predictions (raw + ensembled)
        pw.isdm_blue_whale,
        pw.isdm_fin_whale,
        pw.isdm_humpback_whale,
        pw.isdm_sperm_whale,
        pw.sdm_right_whale,
        pw.sdm_minke_whale,
        pw.blue_whale_prob,
        pw.fin_whale_prob,
        pw.humpback_whale_prob,
        pw.sperm_whale_prob,
        pw.right_whale_prob,
        pw.minke_whale_prob,
        pw.any_whale_prob,
        pw.max_whale_prob,
        pw.mean_whale_prob,

        -- Static sub-scores from current risk (no proximity)
        cs.cell_lat,
        cs.cell_lon,
        cs.geom,
        cs.traffic_score,
        cs.strike_score,
        cs.protection_gap,
        cs.reference_risk_score,

        -- Feature flags
        cs.has_traffic,
        cs.in_mpa,
        cs.has_strike_history,
        cs.in_speed_zone,
        cs.in_current_sma,
        cs.in_proposed_zone,
        cs.has_nisi_reference,
        cs.h3_cell is not null as has_current_risk,

        -- Raw interaction: projected whale × current traffic threat.
        -- traffic_score is already 0–1 so the product is 0–1.
        coalesce(pw.any_whale_prob, 0)
            * coalesce(cs.traffic_score, 0)
            as whale_traffic_interaction

    from projected_whale pw
    left join current_static cs
        on pw.h3_cell = cs.h3_cell and pw.season = cs.season

),

-- Percentile-rank the whale-dependent metrics within each projection.
-- Static sub-scores are already final — only whale probs need ranking.
ranked as (

    select
        *,

        -- Whale percentiles (for whale_ml_score macro)
        percent_rank() over (
            partition by scenario, decade, season
            order by coalesce(any_whale_prob, 0)
        ) as pctl_any_whale,

        percent_rank() over (
            partition by scenario, decade, season
            order by coalesce(max_whale_prob, 0)
        ) as pctl_max_whale,

        percent_rank() over (
            partition by scenario, decade, season
            order by coalesce(mean_whale_prob, 0)
        ) as pctl_mean_whale,

        -- Interaction percentile
        percent_rank() over (
            partition by scenario, decade, season
            order by whale_traffic_interaction
        ) as interaction_score

    from joined

),

scored as (

    select
        *,

        -- Recompute whale ML sub-score from projected percentiles
        {{ whale_ml_score() }} as whale_ml_score

    from ranked

),

risk_computed as (

    select
        *,
        -- 6-sub-score projected composite (no proximity)
        {{ weighted_risk_score('ml_projected') }} as risk_score
    from scored

)

select
    h3_cell,
    season,
    scenario,
    decade,
    cell_lat,
    cell_lon,
    geom,

    -- ── Composite risk score ────────────────────────
    risk_score,

    -- ── Risk category ───────────────────────────────
    {{ risk_category('risk_score') }} as risk_category,

    -- ── Sub-scores (6 — no proximity) ─────────────────
    round(interaction_score::numeric, 4)       as interaction_score,
    round(traffic_score::numeric, 4)           as traffic_score,
    round(whale_ml_score::numeric, 4)          as whale_ml_score,
    round(strike_score::numeric, 4)            as strike_score,
    round(protection_gap::numeric, 4)          as protection_gap,
    round(reference_risk_score::numeric, 4)    as reference_risk_score,

    -- ── Ensembled whale predictions (6 species) ─────
    round(blue_whale_prob::numeric, 4)         as blue_whale_prob,
    round(fin_whale_prob::numeric, 4)          as fin_whale_prob,
    round(humpback_whale_prob::numeric, 4)     as humpback_whale_prob,
    round(sperm_whale_prob::numeric, 4)        as sperm_whale_prob,
    round(right_whale_prob::numeric, 4)        as right_whale_prob,
    round(minke_whale_prob::numeric, 4)        as minke_whale_prob,
    round(any_whale_prob::numeric, 4)          as any_whale_prob,
    round(max_whale_prob::numeric, 4)          as max_whale_prob,
    round(mean_whale_prob::numeric, 4)         as mean_whale_prob,

    -- ── Raw model predictions (diagnostic) ──────────
    round(isdm_blue_whale::numeric, 4)         as isdm_blue_whale,
    round(isdm_fin_whale::numeric, 4)          as isdm_fin_whale,
    round(isdm_humpback_whale::numeric, 4)     as isdm_humpback_whale,
    round(isdm_sperm_whale::numeric, 4)        as isdm_sperm_whale,
    round(sdm_right_whale::numeric, 4)         as sdm_right_whale,
    round(sdm_minke_whale::numeric, 4)         as sdm_minke_whale,

    -- ── Whale × traffic interaction (raw) ───────────
    round(whale_traffic_interaction::numeric, 4) as whale_traffic_interaction,

    -- ── Feature flags ───────────────────────────────
    has_traffic,
    has_current_risk,
    in_mpa,
    has_strike_history,
    in_speed_zone,
    in_current_sma,
    in_proposed_zone,
    has_nisi_reference

from risk_computed
