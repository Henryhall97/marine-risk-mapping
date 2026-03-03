-- Macro: compute a weighted risk score from sub-score columns.
--
-- Two weight sets are supported:
--   'standard'  → 7 sub-scores (traffic, cetacean, proximity, strike,
--                  habitat, protection_gap, reference)
--   'ml'        → 8 sub-scores (adds interaction + whale_ml, reweights)
--
-- Weights are read from dbt_project.yml vars and validated at compile
-- time to sum to 1.0.  If they don't, dbt build fails immediately.
--
-- Usage:
--   {{ weighted_risk_score('standard') }}   → SQL expression (numeric)
--   {{ weighted_risk_score('ml') }}         → SQL expression (numeric)

{% macro weighted_risk_score(weight_set) %}

{#-- ── Resolve weights from vars ─────────────────────── --#}
{% if weight_set == 'standard' %}
    {% set w_traffic    = var('risk_weight_traffic') %}
    {% set w_cetacean   = var('risk_weight_cetacean') %}
    {% set w_proximity  = var('risk_weight_proximity') %}
    {% set w_strike     = var('risk_weight_strike') %}
    {% set w_habitat    = var('risk_weight_habitat') %}
    {% set w_prot_gap   = var('risk_weight_protection_gap') %}
    {% set w_reference  = var('risk_weight_reference') %}

    {% set weight_sum = w_traffic + w_cetacean + w_proximity
                      + w_strike + w_habitat + w_prot_gap
                      + w_reference %}

    {% if (weight_sum * 100) | round != 100 %}
        {{ exceptions.raise_compiler_error(
            "Standard risk weights sum to "
            ~ weight_sum ~ ", expected 1.0. "
            ~ "Check risk_weight_* vars in dbt_project.yml."
        ) }}
    {% endif %}

    round((
        {{ w_traffic }}  * traffic_score
      + {{ w_cetacean }} * cetacean_score
      + {{ w_proximity }} * proximity_score
      + {{ w_strike }}   * strike_score
      + {{ w_habitat }}  * habitat_score
      + {{ w_prot_gap }} * protection_gap
      + {{ w_reference }} * reference_risk_score
    )::numeric, 4)

{% elif weight_set == 'ml' %}
    {% set w_interaction = var('risk_ml_weight_interaction') %}
    {% set w_traffic     = var('risk_ml_weight_traffic') %}
    {% set w_whale_ml    = var('risk_ml_weight_whale_ml') %}
    {% set w_proximity   = var('risk_ml_weight_proximity') %}
    {% set w_strike      = var('risk_ml_weight_strike') %}
    {% set w_habitat     = var('risk_ml_weight_habitat') %}
    {% set w_prot_gap    = var('risk_ml_weight_protection_gap') %}
    {% set w_reference   = var('risk_ml_weight_reference') %}

    {% set weight_sum = w_interaction + w_traffic + w_whale_ml
                      + w_proximity + w_strike + w_habitat
                      + w_prot_gap + w_reference %}

    {% if (weight_sum * 100) | round != 100 %}
        {{ exceptions.raise_compiler_error(
            "ML risk weights sum to "
            ~ weight_sum ~ ", expected 1.0. "
            ~ "Check risk_ml_weight_* vars in dbt_project.yml."
        ) }}
    {% endif %}

    round((
        {{ w_interaction }} * interaction_score
      + {{ w_traffic }}     * traffic_score
      + {{ w_whale_ml }}    * whale_ml_score
      + {{ w_proximity }}   * proximity_score
      + {{ w_strike }}      * strike_score
      + {{ w_habitat }}     * habitat_score
      + {{ w_prot_gap }}    * protection_gap
      + {{ w_reference }}   * reference_risk_score
    )::numeric, 4)

{% else %}
    {{ exceptions.raise_compiler_error(
        "Unknown weight_set '" ~ weight_set ~ "'. "
        ~ "Use 'standard' or 'ml'."
    ) }}
{% endif %}

{% endmacro %}
