-- Sub-score macros for collision risk models.
--
-- Each macro reads its weights from dbt_project.yml vars and emits
-- the SQL expression for that sub-score.  All collision risk marts
-- call these macros so the weights live in exactly one place.
--
-- Every weight set is validated at compile time to sum to 1.0.
--
-- ═══════════════════════════════════════════════════════════════
-- SCORING METHODOLOGY NOTES
-- ═══════════════════════════════════════════════════════════════
--
-- 1. ALL SCORES ARE RELATIVE (percentile-ranked)
--    Every numeric feature is mapped to [0, 1] via percent_rank()
--    in the calling mart before these macros execute.  A score of
--    0.75 means "higher than 75 % of H3 cells" — NOT a 75 %
--    probability.  This avoids scale-sensitivity across features
--    with wildly different units (knots, counts, km, boolean) and
--    makes sub-scores directly comparable.
--
-- 2. WEIGHTS ARE EXPERT-ELICITED
--    Composite and sub-score weights were set through structured
--    expert judgement informed by:
--      • Vanderlaan & Taggart (2007) — speed-lethality logistic
--      • Rockwood et al. (2021) — co-occurrence risk framework
--      • Nisi et al. (2024) — global ship-strike risk methodology
--      • NOAA ship strike reduction strategy (2024)
--    They are NOT empirically optimised (no data-fitting).  The
--    ML-enhanced mart (fct_collision_risk_ml) provides a data-
--    driven comparison via XGBoost feature importance.
--
-- 3. STRIKE SUB-SCORE IS EFFECTIVELY BINARY
--    Only 67 of ~1.8 M cells have any recorded ship strikes.
--    percent_rank() maps all 1.8 M zero-strike cells to 0 and
--    spreads the 67 non-zero cells across (0, 1].  The sub-score
--    therefore functions as a sparse historical hotspot indicator
--    rather than a graduated risk curve.  Its 10 % composite
--    weight is intentionally modest.
--
-- 4. PROXIMITY BLEND — INTENTIONAL OVERLAP
--    The proximity sub-score blends whale proximity, ship
--    proximity, and strike proximity using exponential decay.
--    Whale proximity correlates with cetacean sighting density
--    and ship proximity correlates with traffic intensity.  This
--    is intentional: proximity captures *spatial co-location
--    gradients* (distance to the nearest hotspot), while the
--    cetacean and traffic sub-scores capture the *magnitude* of
--    activity within each cell.  The two perspectives are
--    complementary — a cell can have low local sightings yet be
--    close to a major whale aggregation.  The geometric-mean
--    formulation (√(whale_prox × ship_prox)) further ensures
--    that proximity scores are high only when BOTH whales and
--    ships are nearby, not just one.
--
-- 5. SPECIES VARIATION
--    The standard mart is species-agnostic: it treats all cetacean
--    sightings equally (with a baleen bonus).  Species-specific
--    habitat preferences (thermal niche, depth preference, prey
--    fields) are captured by the ML mart's ISDM predictions,
--    which were trained on SST, MLD, SLA, PP, depth, and depth_sd
--    for 4 key species (blue, fin, humpback, sperm whale).  The
--    interaction_score in fct_collision_risk_ml directly measures
--    P(species present) × traffic threat per Rockwood et al.
--
-- 6. HABITAT SCORE — BATHYMETRY + OCEAN PRODUCTIVITY
--    Habitat is a two-level composite: 80 % geomorphology
--    (shelf, shelf-edge, depth zone) and 20 % ocean productivity
--    (percentile-ranked primary production, pp_upper_200m).
--    PP is the most species-agnostic ocean indicator: higher
--    productivity → more prey → more cetaceans universally.
--    ISDM feature importance shows PP ranks 5th–6th (9–13 %)
--    across all 4 modelled species, supporting a modest weight.
--    SST and MLD are stronger predictors but species-directional
--    (warm SST helps sperm whales, hurts right whales), so they
--    cannot be percentile-ranked in a species-agnostic score.
--    Seasonal ocean covariates (SST, MLD, SLA) are passed through
--    for ML feature extraction but not scored directly.
--    TODO: revisit ocean weight when species-weighted habitat or
--    ML mart promotion is considered.
-- ═══════════════════════════════════════════════════════════════


-- ── Traffic threat sub-score (0–1) ─────────────────────────
-- 8 percentile-ranked traffic components.
-- V&T speed-lethality dominates (20 %) because literature shows
-- speed is the primary determinant of strike fatality.

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
-- Baleen whales receive equal weight to total sightings because
-- large baleen species (right, humpback, fin) are the primary
-- strike victims.  Recent sightings (post-2019) are weighted
-- 30 % to up-weight areas with continuing whale presence.

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
-- NOTE: effectively binary — only 67 of ~1.8 M cells have any
-- strikes.  All zero-strike cells tie at percent_rank = 0.
-- Fatal strikes (35 %) are weighted higher than total (40 %)
-- relative to their count because they indicate locations where
-- encounters are not just frequent but lethal.

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
-- Two-level composite:
--   Outer: bathymetry (80 %) vs ocean productivity (20 %)
--   Inner: continental shelf (50 %) + shelf edge (30 %) + depth zone (20 %)
-- Ocean component uses percentile-ranked primary production
-- (pp_upper_200m) — universally positive for cetacean habitat.
-- ISDM importance analysis shows PP at 9–13 % across species,
-- supporting this modest 20 % outer weight.  SST/MLD are stronger
-- but species-directional so omitted from the species-agnostic score.
-- TODO: revisit if species-weighted habitat scoring is added.

{% macro habitat_score() %}

{# ── Outer weights: bathymetry vs ocean ── #}
{% set w_bathy = var('habitat_w_bathymetry') %}
{% set w_ocean = var('habitat_w_ocean') %}
{% set outer_total = w_bathy + w_ocean %}
{% if (outer_total * 100) | round != 100 %}
    {{ exceptions.raise_compiler_error("habitat_score outer weights sum to " ~ outer_total ~ ", expected 1.0") }}
{% endif %}

{# ── Inner bathymetry weights ── #}
{% set w_shelf = var('habitat_w_shelf') %}
{% set w_edge  = var('habitat_w_edge') %}
{% set w_dz    = var('habitat_w_depth_zone') %}
{% set inner_total = w_shelf + w_edge + w_dz %}
{% if (inner_total * 100) | round != 100 %}
    {{ exceptions.raise_compiler_error("habitat_score bathymetry weights sum to " ~ inner_total ~ ", expected 1.0") }}
{% endif %}

{% set dz_shelf   = var('depth_zone_shelf') %}
{% set dz_slope   = var('depth_zone_slope') %}
{% set dz_abyssal = var('depth_zone_abyssal') %}

(
    {{ w_bathy }} * (
        {{ w_shelf }} * coalesce(is_continental_shelf::int, 0)
      + {{ w_edge }}  * coalesce(is_shelf_edge::int, 0)
      + {{ w_dz }}    * case coalesce(depth_zone, 'unknown')
                           when 'shelf'   then {{ dz_shelf }}
                           when 'slope'   then {{ dz_slope }}
                           when 'abyssal' then {{ dz_abyssal }}
                           else 0.0
                       end
    )
  + {{ w_ocean }} * coalesce(pctl_ocean_productivity, 0)
)

{% endmacro %}


-- ── Protection gap sub-score (0–1) ─────────────────────────
-- Tiered CASE: lower score = better protected.
--
-- Proposed speed zones are EXCLUDED — they represent areas
-- identified as risky, not areas that are actually protected.
-- Including them inverted the signal: corridors deemed
-- dangerous enough to warrant a proposal scored as "protected".
--
-- SMAs are voluntary speed advisories (limited enforcement),
-- so they provide only a small bonus on top of real spatial
-- protection (MPAs / no-take zones).  Standing alone, an SMA
-- is scored only marginally better than no protection at all.

{% macro protection_gap_score() %}
case
    when coalesce(has_no_take_zone, false) and coalesce(in_current_sma, false)
        then {{ var('protection_notake_and_sma') }}
    when coalesce(has_no_take_zone, false)
        then {{ var('protection_notake_only') }}
    when coalesce(has_strict_protection, false) and coalesce(in_current_sma, false)
        then {{ var('protection_strict_and_sma') }}
    when coalesce(has_strict_protection, false)
        then {{ var('protection_strict_mpa') }}
    when in_mpa and coalesce(in_current_sma, false)
        then {{ var('protection_mpa_and_sma') }}
    when in_mpa
        then {{ var('protection_any_mpa') }}
    when coalesce(in_current_sma, false)
        then {{ var('protection_sma_only') }}
    else {{ var('protection_none') }}
end
{% endmacro %}


-- ── Proximity blend sub-score (0–1) ────────────────────────
-- Whale×ship geometric mean (45 %), strike proximity (30 %),
-- protection gap (25 %).
-- NOTE — intentional overlap with cetacean and traffic sub-scores:
-- proximity captures spatial *gradients* (distance to nearest
-- hotspot) while density sub-scores capture *magnitude* within
-- each cell.  The geometric mean √(whale × ship) ensures high
-- proximity scores require BOTH whales and ships nearby.
-- Protection gap component (1 − protection_proximity_score)
-- highlights cells far from any MPA/speed zone.

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
