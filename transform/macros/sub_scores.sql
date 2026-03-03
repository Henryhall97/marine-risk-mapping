-- Sub-score macros for collision risk models.
--
-- Each macro reads its weights from dbt_project.yml vars and emits
-- the SQL expression for that sub-score.  All collision risk marts
-- call these macros so the weights live in exactly one place.
--
-- Every weight set is validated at compile time to sum to 1.0.


-- ── Traffic threat sub-score (0–1) ─────────────────────────
-- 8 percentile-ranked traffic components.

{% macro traffic_score() %}

{% set w = {
    'speed_lethality':      var('traffic_w_speed_lethality'),
    'high_speed_fraction':  var('traffic_w_high_speed_fraction'),
    'vessels':              var('traffic_w_vessels'),
    'large_vessels':        var('traffic_w_large_vessels'),
    'draft_risk':           var('traffic_w_draft_risk'),
    'draft_risk_fraction':  var('traffic_w_draft_risk_fraction'),
    'commercial':           var('traffic_w_commercial'),
    'night_traffic':        var('traffic_w_night_traffic'),
} %}
{% set s = w.values() | list %}
{% set total = s[0] + s[1] + s[2] + s[3] + s[4] + s[5] + s[6] + s[7] %}
{% if (total * 100) | round != 100 %}
    {{ exceptions.raise_compiler_error("traffic_score weights sum to " ~ total ~ ", expected 1.0") }}
{% endif %}

(
    {{ w.speed_lethality }}     * pctl_speed_lethality
  + {{ w.high_speed_fraction }} * pctl_high_speed_fraction
  + {{ w.vessels }}             * pctl_vessels
  + {{ w.large_vessels }}       * pctl_large_vessels
  + {{ w.draft_risk }}          * pctl_draft_risk
  + {{ w.draft_risk_fraction }} * pctl_draft_risk_fraction
  + {{ w.commercial }}          * pctl_commercial
  + {{ w.night_traffic }}       * pctl_night_traffic
)

{% endmacro %}


-- ── Cetacean exposure sub-score (0–1) ──────────────────────
-- 3 components: total sightings, baleen whales, recent sightings.

{% macro cetacean_score() %}

{% set w_sightings = var('cetacean_w_sightings') %}
{% set w_baleen    = var('cetacean_w_baleen') %}
{% set w_recent    = var('cetacean_w_recent') %}
{% set total = w_sightings + w_baleen + w_recent %}
{% if (total * 100) | round != 100 %}
    {{ exceptions.raise_compiler_error("cetacean_score weights sum to " ~ total ~ ", expected 1.0") }}
{% endif %}

(
    {{ w_sightings }} * pctl_sightings
  + {{ w_baleen }}    * pctl_baleen
  + {{ w_recent }}    * pctl_recent_sightings
)

{% endmacro %}


-- ── ML whale exposure sub-score (0–1) ──────────────────────
-- 3 ISDM probability percentiles (fct_collision_risk_ml only).

{% macro whale_ml_score() %}

{% set w_any  = var('whale_ml_w_any') %}
{% set w_max  = var('whale_ml_w_max') %}
{% set w_mean = var('whale_ml_w_mean') %}
{% set total = w_any + w_max + w_mean %}
{% if (total * 100) | round != 100 %}
    {{ exceptions.raise_compiler_error("whale_ml_score weights sum to " ~ total ~ ", expected 1.0") }}
{% endif %}

(
    {{ w_any }}  * pctl_any_whale
  + {{ w_max }}  * pctl_max_whale
  + {{ w_mean }} * pctl_mean_whale
)

{% endmacro %}


-- ── Strike history sub-score (0–1) ─────────────────────────
-- 3 components: total, fatal, and baleen strikes.

{% macro strike_score() %}

{% set w_total  = var('strike_w_total') %}
{% set w_fatal  = var('strike_w_fatal') %}
{% set w_baleen = var('strike_w_baleen') %}
{% set total = w_total + w_fatal + w_baleen %}
{% if (total * 100) | round != 100 %}
    {{ exceptions.raise_compiler_error("strike_score weights sum to " ~ total ~ ", expected 1.0") }}
{% endif %}

(
    {{ w_total }}  * pctl_strikes
  + {{ w_fatal }}  * pctl_fatal_strikes
  + {{ w_baleen }} * pctl_baleen_strikes
)

{% endmacro %}


-- ── Habitat suitability sub-score (0–1) ────────────────────
-- Continental shelf, shelf-edge, and depth zone scoring.

{% macro habitat_score() %}

{% set w_shelf = var('habitat_w_shelf') %}
{% set w_edge  = var('habitat_w_edge') %}
{% set w_dz    = var('habitat_w_depth_zone') %}
{% set total = w_shelf + w_edge + w_dz %}
{% if (total * 100) | round != 100 %}
    {{ exceptions.raise_compiler_error("habitat_score weights sum to " ~ total ~ ", expected 1.0") }}
{% endif %}

{% set dz_shelf   = var('depth_zone_shelf') %}
{% set dz_slope   = var('depth_zone_slope') %}
{% set dz_abyssal = var('depth_zone_abyssal') %}

(
    {{ w_shelf }} * coalesce(is_continental_shelf::int, 0)
  + {{ w_edge }}  * coalesce(is_shelf_edge::int, 0)
  + {{ w_dz }}    * case coalesce(depth_zone, 'unknown')
                       when 'shelf'   then {{ dz_shelf }}
                       when 'slope'   then {{ dz_slope }}
                       when 'abyssal' then {{ dz_abyssal }}
                       else 0.0
                   end
)

{% endmacro %}


-- ── Protection gap sub-score (0–1) ─────────────────────────
-- Tiered CASE: lower score = better protected.

{% macro protection_gap_score() %}
case
    when coalesce(in_current_sma, false) and coalesce(has_no_take_zone, false)
        then {{ var('protection_sma_and_notake') }}
    when coalesce(in_current_sma, false)
        then {{ var('protection_sma_only') }}
    when coalesce(in_proposed_zone, false) and in_mpa
        then {{ var('protection_proposed_and_mpa') }}
    when coalesce(has_no_take_zone, false)
        then {{ var('protection_notake_only') }}
    when coalesce(in_proposed_zone, false)
        then {{ var('protection_proposed_only') }}
    when coalesce(has_strict_protection, false)
        then {{ var('protection_strict_mpa') }}
    when in_mpa
        then {{ var('protection_any_mpa') }}
    else {{ var('protection_none') }}
end
{% endmacro %}


-- ── Proximity blend sub-score (0–1) ────────────────────────
-- Whale×ship geometric mean, strike proximity, protection gap.

{% macro proximity_score() %}

{% set w_ws   = var('proximity_w_whale_ship') %}
{% set w_st   = var('proximity_w_strike') %}
{% set w_prot = var('proximity_w_protection') %}
{% set total = w_ws + w_st + w_prot %}
{% if (total * 100) | round != 100 %}
    {{ exceptions.raise_compiler_error("proximity_score weights sum to " ~ total ~ ", expected 1.0") }}
{% endif %}

(
    {{ w_ws }}   * sqrt(
        coalesce(whale_proximity_score, 0)
      * coalesce(ship_proximity_score, 0)
    )
  + {{ w_st }}   * coalesce(strike_proximity_score, 0)
  + {{ w_prot }} * (1.0 - coalesce(protection_proximity_score, 0))
)

{% endmacro %}
