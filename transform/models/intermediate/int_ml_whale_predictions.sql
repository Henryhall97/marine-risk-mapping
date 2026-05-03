-- Intermediate model: ML whale presence predictions per hex cell per season
--
-- Joins ISDM (Integrated Species Distribution Model) predictions to the
-- hex grid spine. Each ISDM model predicts P(species present) for one of
-- four species: blue, fin, humpback, sperm whale.

{{ config(
    indexes=[
        {'columns': ['h3_cell', 'season']},
    ]
) }}
--
-- Derived columns:
--   - max_whale_prob:  highest P(present) across all 4 species
--   - mean_whale_prob: average P(present) across all 4 species
--   - any_whale_prob:  P(any whale present) = 1 - ∏(1 - P_i)
--
-- any_whale_prob is the most principled composite — it models
-- the probability that *at least one* of the four species is present,
-- assuming independence between species distributions.
--
-- Grain: one row per (h3_cell, season).

with predictions as (

    select
        h3_cell,
        season,
        isdm_blue_whale,
        isdm_fin_whale,
        isdm_humpback_whale,
        isdm_sperm_whale
    from {{ source('marine_risk', 'ml_whale_predictions') }}

)

select
    p.h3_cell,
    p.season,

    -- Per-species predicted probabilities
    p.isdm_blue_whale,
    p.isdm_fin_whale,
    p.isdm_humpback_whale,
    p.isdm_sperm_whale,

    -- Composite: maximum across species
    greatest(
        p.isdm_blue_whale,
        p.isdm_fin_whale,
        p.isdm_humpback_whale,
        p.isdm_sperm_whale
    ) as max_whale_prob,

    -- Composite: mean across species
    (
        coalesce(p.isdm_blue_whale, 0)
      + coalesce(p.isdm_fin_whale, 0)
      + coalesce(p.isdm_humpback_whale, 0)
      + coalesce(p.isdm_sperm_whale, 0)
    ) / 4.0 as mean_whale_prob,

    -- Composite: P(any whale) = 1 - ∏(1 - P_i)
    -- Most principled: probability at least one species is present
    1.0 - (
        (1.0 - coalesce(p.isdm_blue_whale, 0))
      * (1.0 - coalesce(p.isdm_fin_whale, 0))
      * (1.0 - coalesce(p.isdm_humpback_whale, 0))
      * (1.0 - coalesce(p.isdm_sperm_whale, 0))
    ) as any_whale_prob

from predictions p
inner join {{ ref('int_hex_grid') }} g
    on p.h3_cell = g.h3_cell
