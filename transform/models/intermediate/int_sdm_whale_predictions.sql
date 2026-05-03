-- Intermediate model: SDM (OBIS-trained) whale predictions per hex cell per season
--
-- Mirrors int_ml_whale_predictions but for the OBIS-trained SDM rather than
-- the Nisi-trained ISDM.  Predictions are out-of-fold (OOF) from 5-fold
-- spatial block CV — each cell's probability comes from a model that never

{{ config(
    indexes=[
        {'columns': ['h3_cell', 'season']},
    ]
) }}
-- saw it during training.  This makes them directly comparable to ISDM scores.
--
-- Key difference from ISDM:
--   - SDM is trained on OBIS opportunistic sighting data (detection bias)
--   - ISDM is trained on Nisi et al. expert-curated presence/absence data
--   - Comparing the two reveals survey-effort bias and validates predictions
--
-- Includes a directly trained any_whale composite (sdm_any_whale) which
-- captures species co-occurrence, plus per-species predictions and computed
-- composites (max, mean, joint) for consistency with the ISDM model.
--
-- Grain: one row per (h3_cell, season).

with predictions as (

    select
        h3_cell,
        season,
        sdm_any_whale,
        sdm_blue_whale,
        sdm_fin_whale,
        sdm_humpback_whale,
        sdm_sperm_whale,
        sdm_right_whale,
        sdm_minke_whale
    from {{ source('marine_risk', 'ml_sdm_predictions') }}

)

select
    p.h3_cell,
    p.season,

    -- Directly trained aggregate: P(any whale | OBIS)
    p.sdm_any_whale,

    -- Per-species predicted probabilities
    p.sdm_blue_whale,
    p.sdm_fin_whale,
    p.sdm_humpback_whale,
    p.sdm_sperm_whale,
    p.sdm_right_whale,
    p.sdm_minke_whale,

    -- Composite: maximum across the 6 per-species models
    greatest(
        p.sdm_blue_whale,
        p.sdm_fin_whale,
        p.sdm_humpback_whale,
        p.sdm_sperm_whale,
        p.sdm_right_whale,
        p.sdm_minke_whale
    ) as max_whale_prob,

    -- Composite: mean across the 6 per-species models
    (
        coalesce(p.sdm_blue_whale, 0)
      + coalesce(p.sdm_fin_whale, 0)
      + coalesce(p.sdm_humpback_whale, 0)
      + coalesce(p.sdm_sperm_whale, 0)
      + coalesce(p.sdm_right_whale, 0)
      + coalesce(p.sdm_minke_whale, 0)
    ) / 6.0 as mean_whale_prob,

    -- Composite: P(any whale) = 1 - ∏(1 - P_i) via independence
    -- Compare this with sdm_any_whale (directly trained) to see
    -- whether species co-occurrence matters
    1.0 - (
        (1.0 - coalesce(p.sdm_blue_whale, 0))
      * (1.0 - coalesce(p.sdm_fin_whale, 0))
      * (1.0 - coalesce(p.sdm_humpback_whale, 0))
      * (1.0 - coalesce(p.sdm_sperm_whale, 0))
      * (1.0 - coalesce(p.sdm_right_whale, 0))
      * (1.0 - coalesce(p.sdm_minke_whale, 0))
    ) as any_whale_prob_joint

from predictions p
inner join {{ ref('int_hex_grid') }} g
    on p.h3_cell = g.h3_cell
