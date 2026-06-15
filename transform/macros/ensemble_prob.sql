-- Ensemble whale-probability macro (ISDM + SDM).
--
-- Combines an ISDM prediction and an SDM prediction for a single
-- species into one ensembled P(present).  Used by every ML risk mart
-- (fct_collision_risk_ml, fct_collision_risk_ml_projected,
-- fct_whale_vessel_exposure) so the ensemble rule lives in ONE place.
--
-- ── Phase 1b item (A): NULL-DEFLATION BUGFIX ──────────────────
-- The previous inline form `(coalesce(isdm,0)+coalesce(sdm,0))/2.0`
-- treated a MISSING model prediction as a hard zero and still divided
-- by two — so a cell covered by only ONE model had its whale
-- probability HALVED for a coverage reason, not a biological one.
-- ISDM has narrower spatial/species coverage than SDM, so this
-- silently deflated P(whale) across large areas and propagated into
-- any/max/mean_whale_prob AND the Rockwood P(whale)×traffic
-- interaction.  This macro is NULL-AWARE: it averages only over the
-- models actually present (one model present ⇒ use it directly, never
-- halved; both absent ⇒ 0).
--
-- ── Phase 1b item (D): SKILL-WEIGHTED ENSEMBLE ────────────────
-- When BOTH models predict a cell, they are combined with per-species
-- weights instead of a flat 50/50.  The weights reflect each model's
-- per-species spatial-CV skill (ISDM expert-integrated data vs SDM
-- OBIS presence-background); they are stored as dbt vars
-- `ensemble_w_isdm_<species>` / `ensemble_w_sdm_<species>` (each pair
-- sums to 1.0) so a sensitivity test only edits dbt_project.yml.
-- SDM-only species (right whale, minke) have no ISDM counterpart and
-- continue to use the SDM value directly — they never call this macro.
--
-- Args:
--   isdm_col  — fully-qualified ISDM column (e.g. 'ml.isdm_blue_whale')
--   sdm_col   — fully-qualified SDM column  (e.g. 'sdm.sdm_blue_whale')
--   species   — short key for the weight vars ('blue'/'fin'/'humpback'/'sperm')

{% macro ensemble_prob(isdm_col, sdm_col, species) %}
{%- set w_isdm = var('ensemble_w_isdm_' ~ species) -%}
{%- set w_sdm = var('ensemble_w_sdm_' ~ species) -%}
{%- set total = w_isdm + w_sdm -%}
{%- if (total * 100) | round != 100 -%}
    {{ exceptions.raise_compiler_error(
        "ensemble weights for " ~ species ~ " sum to " ~ total ~ ", expected 1.0"
    ) }}
{%- endif -%}
(case
    when {{ isdm_col }} is not null and {{ sdm_col }} is not null
        then {{ w_isdm }} * {{ isdm_col }} + {{ w_sdm }} * {{ sdm_col }}
    when {{ isdm_col }} is not null then {{ isdm_col }}
    when {{ sdm_col }} is not null then {{ sdm_col }}
    else 0.0
end)
{% endmacro %}
