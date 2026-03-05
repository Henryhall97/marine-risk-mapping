-- Mart: ML-enhanced seasonal whale–vessel collision risk
--
-- Same architecture as fct_collision_risk_seasonal but replaces the
-- raw-sighting-based cetacean sub-score with ML-predicted P(whale)
-- from ISDM (Integrated Species Distribution Models).
--
-- Why this is better:
--   1. ISDM models generalize whale presence across the full grid,
--      not just cells with OBIS observation effort.
--   2. P(whale) × traffic interaction directly measures co-occurrence
--      risk rather than independently scoring whale presence and traffic.
--   3. Per-species probabilities allow species-weighted risk (endangered
--      species like right whale can get higher weight in future).
--
-- TODO: species-vulnerability-weighted composite — replace equal-weight
-- any_whale_prob with Σ wᵢ·Pᵢ where wᵢ reflects IUCN status or
-- population size.  See TODO.md for details.
--
-- Sub-score architecture (7 sub-scores, interaction-first):
--   - Whale×traffic interaction 30%  (P(whale) × traffic_threat — PRIMARY)
--   - Traffic threat      15%  (V&T lethality, draft, volume, vessel type, night)
--   - Whale exposure      15%  (residual ML whale presence)
--   - Proximity           15%  (unchanged)
--   - Strike history      10%  (unchanged)
--   - Protection gap      10%  (unchanged)
--   - Reference risk       5%  (unchanged)
--
-- Habitat suitability is deliberately OMITTED from the ML mart.
-- The ISDM models were trained on all 7 environmental covariates
-- (SST, MLD, SLA, PP, depth, depth_range), so habitat information
-- is already encoded in the whale probability predictions.  Including
-- a separate hand-tuned habitat sub-score would double-count that
-- signal.  This provides clean separation: the standard mart uses
-- expert-elicited habitat weights, the ML mart delegates habitat
-- entirely to the learned species distribution models.
--
-- The interaction score captures Rockwood et al. (2021) co-occurrence:
--   risk = P(whale present) × P(lethal encounter | traffic).
-- Traffic threat uses Vanderlaan & Taggart (2007) speed-lethality logistic
-- and vessel draft (vertical strike zone) instead of binary >10kn threshold.
--
-- Grain: one row per (h3_cell, season). ~7.3M rows.

{{ config(
    indexes=[
        {'columns': ['h3_cell', 'season']},
        {'columns': ['risk_score']},
        {'columns': ['geom'], 'type': 'gist'},
    ]
) }}

with seasons as (

    select unnest(array['winter', 'spring', 'summer', 'fall']) as season

),

-- Expand hex grid × 4 seasons as the spine
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

        -- ── ML whale predictions (REPLACES raw sightings) ──
        ml.isdm_blue_whale,
        ml.isdm_fin_whale,
        ml.isdm_humpback_whale,
        ml.isdm_sperm_whale,
        ml.max_whale_prob,
        ml.mean_whale_prob,
        ml.any_whale_prob,

        -- ── Seasonal traffic ───────────────────────────
        t.months_active,
        t.total_pings,
        t.avg_monthly_vessels,
        t.peak_monthly_vessels,
        t.avg_speed_knots,
        t.peak_speed_knots,
        t.avg_high_speed_vessels,
        t.total_high_speed_pings,
        t.avg_large_vessels,
        t.avg_vessel_length_m,
        t.avg_deep_draft_vessels,
        t.avg_speed_lethality,
        t.avg_high_speed_fraction,
        t.avg_draft_risk_fraction,
        t.avg_draft_imputed_m,
        t.avg_cog_diversity,
        t.avg_night_vessels,
        t.avg_night_high_speed,
        t.night_traffic_ratio,
        t.avg_commercial_vessels,
        t.avg_fishing_vessels,
        t.avg_passenger_vessels,

        -- ── Static: bathymetry ─────────────────────────
        b.depth_m,
        b.depth_range_m,
        b.is_continental_shelf,
        b.is_shelf_edge,
        b.depth_zone,

        -- ── Static: MPA ────────────────────────────────
        m.mpa_count,
        m.has_strict_protection,
        m.has_no_take_zone,

        -- ── Static: proximity ──────────────────────────
        p.dist_to_nearest_whale_km,
        p.dist_to_nearest_ship_km,
        p.dist_to_nearest_strike_km,
        p.dist_to_nearest_protection_km,
        p.whale_proximity_score,
        p.ship_proximity_score,
        p.strike_proximity_score,
        p.protection_proximity_score,

        -- ── Static: strike history ─────────────────────
        ss.total_strikes,
        ss.fatal_strikes,
        ss.serious_injury_strikes,
        ss.baleen_strikes,
        ss.right_whale_strikes,

        -- ── Seasonal: speed zone ───────────────────────
        coalesce(sz.in_speed_zone, false)    as in_speed_zone,
        coalesce(sz.in_current_sma, false)   as in_current_sma,
        coalesce(sz.in_proposed_zone, false) as in_proposed_zone,
        sz.zone_count,
        sz.max_season_days,

        -- ── Static: Nisi reference ─────────────────────
        nr.nisi_all_risk,
        nr.nisi_shipping_index,
        nr.nisi_whale_space_use,
        nr.nisi_hotspot_overlap,

        -- ── Seasonal: ocean covariates ─────────────────
        oc.sst,
        oc.sst_sd,
        oc.mld,
        oc.sla,
        oc.pp_upper_200m,

        -- Convenience booleans
        t.h3_cell is not null      as has_traffic,
        ml.h3_cell is not null     as has_ml_predictions,
        m.h3_cell is not null      as in_mpa,
        ss.h3_cell is not null     as has_strike_history,
        nr.h3_cell is not null     as has_nisi_reference

    from grid_seasons gs
    left join {{ ref('int_ml_whale_predictions') }} ml
        on gs.h3_cell = ml.h3_cell and gs.season = ml.season
    left join {{ ref('int_vessel_traffic_seasonal') }} t
        on gs.h3_cell = t.h3_cell and gs.season = t.season
    left join {{ ref('int_bathymetry') }} b
        on gs.h3_cell = b.h3_cell
    left join {{ ref('int_mpa_coverage') }} m
        on gs.h3_cell = m.h3_cell
    left join {{ ref('int_proximity') }} p
        on gs.h3_cell = p.h3_cell
    left join {{ ref('int_ship_strike_density') }} ss
        on gs.h3_cell = ss.h3_cell
    left join {{ ref('int_speed_zone_coverage_seasonal') }} sz
        on gs.h3_cell = sz.h3_cell and gs.season = sz.season
    left join {{ ref('int_nisi_reference_risk') }} nr
        on gs.h3_cell = nr.h3_cell
    left join {{ ref('int_ocean_covariates_seasonal') }} oc
        on gs.h3_cell = oc.h3_cell and gs.season = oc.season

    -- Exclude non-ocean cells (Natural Earth ocean mask)
    where coalesce(b.is_ocean, false) = true

),

ranked as (

    -- Percentile-rank WITHIN each season
    select
        *,

        -- Traffic percentiles (same as fct_collision_risk_seasonal)
        percent_rank() over (partition by season order by coalesce(avg_monthly_vessels, 0))
            as pctl_vessels,
        percent_rank() over (partition by season order by coalesce(avg_speed_lethality, 0))
            as pctl_speed_lethality,
        percent_rank() over (partition by season order by coalesce(avg_large_vessels, 0))
            as pctl_large_vessels,
        percent_rank() over (partition by season order by coalesce(avg_draft_imputed_m, 0))
            as pctl_draft_risk,
        percent_rank() over (partition by season order by coalesce(avg_high_speed_fraction, 0))
            as pctl_high_speed_fraction,
        percent_rank() over (partition by season order by coalesce(avg_draft_risk_fraction, 0))
            as pctl_draft_risk_fraction,
        percent_rank() over (partition by season order by coalesce(avg_commercial_vessels, 0))
            as pctl_commercial,
        percent_rank() over (partition by season order by coalesce(avg_night_vessels, 0))
            as pctl_night_traffic,

        -- ML whale percentiles (REPLACES raw sighting percentiles)
        -- These are already calibrated probabilities (0–1) from the ISDM models,
        -- but we still percentile-rank them for consistency with the sub-score
        -- framework (all sub-scores must be 0–1 percentile-ranked).
        percent_rank() over (partition by season order by coalesce(any_whale_prob, 0))
            as pctl_any_whale,
        percent_rank() over (partition by season order by coalesce(max_whale_prob, 0))
            as pctl_max_whale,
        percent_rank() over (partition by season order by coalesce(mean_whale_prob, 0))
            as pctl_mean_whale,

        -- Strike percentiles (same across seasons — static data)
        percent_rank() over (partition by season order by coalesce(total_strikes, 0))
            as pctl_strikes,
        percent_rank() over (partition by season order by coalesce(fatal_strikes, 0))
            as pctl_fatal_strikes,
        percent_rank() over (partition by season order by coalesce(baleen_strikes, 0))
            as pctl_baleen_strikes,

        -- Nisi reference percentile
        percent_rank() over (partition by season order by coalesce(nisi_all_risk, 0))
            as pctl_nisi_risk,

        -- Ocean productivity percentile (higher PP = better whale habitat)
        percent_rank() over (partition by season order by coalesce(pp_upper_200m, 0))
            as pctl_ocean_productivity

    from features

),

scored as (

    select
        *,

        -- ── Traffic threat sub-score (V&T lethality + draft) ────
        {{ traffic_score() }} as traffic_score,

        -- ── ML whale exposure sub-score (REPLACES raw cetacean_score) ──
        {{ whale_ml_score() }} as whale_ml_score,

        -- ── Strike history sub-score ────────────────────────────
        {{ strike_score() }} as strike_score,

        -- (No habitat sub-score — ISDM predictions already encode
        --  habitat via the 7 env covariates they were trained on.
        --  See weighted_risk_score.sql header for rationale.)

        -- ── Protection gap ──────────────────────────────────────
        {{ protection_gap_score() }} as protection_gap,

        -- ── Proximity sub-score ─────────────────────────────────
        {{ proximity_score() }} as proximity_score,

        -- ── Reference risk ──────────────────────────────────────
        pctl_nisi_risk as reference_risk_score,

        -- ── Whale × traffic interaction ─────────────────────────
        -- P(any whale) × traffic_threat. Promoted to primary
        -- co-occurrence metric (25% of composite). Percentile-ranked
        -- in the interaction_ranked CTE before inclusion.
        coalesce(any_whale_prob, 0) * {{ traffic_score() }}
            as whale_traffic_interaction

    from ranked

),

interaction_ranked as (

    -- Percentile-rank the whale × traffic interaction within season.
    -- Converts the skewed P(whale) × traffic product to a uniform
    -- 0–1 scale compatible with other sub-scores.
    select
        *,
        percent_rank() over (
            partition by season
            order by whale_traffic_interaction
        ) as interaction_score

    from scored

),

risk_computed as (
    select
        *,
        {{ weighted_risk_score('ml') }} as risk_score
    from interaction_ranked
)

select
    h3_cell,
    season,
    cell_lat,
    cell_lon,
    geom,

    -- ── Composite risk score ────────────────────────
    risk_score,

    -- ── Risk category ───────────────────────────────
    {{ risk_category('risk_score') }} as risk_category,

    -- ── Sub-scores ──────────────────────────────────
    round(interaction_score::numeric, 4)       as interaction_score,
    round(traffic_score::numeric, 4)           as traffic_score,
    round(whale_ml_score::numeric, 4)          as whale_ml_score,
    round(proximity_score::numeric, 4)         as proximity_score,
    round(strike_score::numeric, 4)            as strike_score,
    round(protection_gap::numeric, 4)          as protection_gap,
    round(reference_risk_score::numeric, 4)    as reference_risk_score,

    -- ── ML whale predictions (per-species) ──────────
    round(isdm_blue_whale::numeric, 4)         as isdm_blue_whale,
    round(isdm_fin_whale::numeric, 4)          as isdm_fin_whale,
    round(isdm_humpback_whale::numeric, 4)     as isdm_humpback_whale,
    round(isdm_sperm_whale::numeric, 4)        as isdm_sperm_whale,
    round(any_whale_prob::numeric, 4)          as any_whale_prob,
    round(max_whale_prob::numeric, 4)          as max_whale_prob,
    round(mean_whale_prob::numeric, 4)         as mean_whale_prob,

    -- ── Whale × traffic interaction (raw + scored) ──
    round(whale_traffic_interaction::numeric, 4) as whale_traffic_interaction,

    -- ── Feature flags ───────────────────────────────
    has_traffic,
    has_ml_predictions,
    in_mpa,
    has_strike_history,
    in_speed_zone,
    in_current_sma,
    in_proposed_zone,
    has_nisi_reference

from risk_computed
