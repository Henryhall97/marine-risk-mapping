-- Intermediate model: vessel traffic per hex cell per month
-- Selects key traffic metrics from the AIS H3 summary for
-- the downstream risk model.
--
-- Uses vessel-weighted (vw_) metrics where available — these
-- correct for AIS ping-rate bias where Class A ships broadcast
-- 15x more than Class B.
--
-- Draft imputation: ~15% of vessels don't report draft. We use
-- OLS regression (draft ~ length) fit on cells with complete data
-- to impute missing cell-average drafts. At the cell-level this
-- achieves R²≈0.63 (r=0.79). aggregate_ais.py also computes
-- per-vessel type-stratified imputation (gold standard) — used
-- when vw_avg_draft_imputed_m is available in the source table.
--
-- Speed-lethality: Vanderlaan & Taggart (2007) logistic applied
-- per-vessel in aggregate_ais.py before averaging (avoids Jensen's
-- inequality). Falls back to cell-average formula if vw_avg_lethality
-- is not yet populated.
--
-- Grain: one row per (h3_cell, month).

with draft_regression as (

    -- Fit draft ~ length OLS from cells with both values reported.
    -- PostgreSQL regr_* functions compute exact OLS coefficients.
    -- R² ≈ 0.63, n ≈ 9.1M cell-months.
    select
        regr_slope(vw_avg_draft_m, vw_avg_length_m)     as draft_slope,
        regr_intercept(vw_avg_draft_m, vw_avg_length_m)  as draft_intercept
    from {{ source('marine_risk', 'ais_h3_summary') }}
    where vw_avg_draft_m is not null
      and vw_avg_length_m is not null

)

select
    a.h3_cell,
    a.month,
    a.cell_lat,
    a.cell_lon,

    -- ── Traffic volume ───────────────────────────────
    a.ping_count,
    a.unique_vessels,

    -- ── Speed (vessel-weighted = debiased) ───────────
    a.vw_avg_speed_knots,
    a.vw_median_speed_knots,
    a.max_speed_knots,
    a.high_speed_pings,
    a.high_speed_vessel_count,

    -- ── Vessel size ──────────────────────────────────
    a.vw_avg_length_m,
    a.max_length_m,
    a.p95_length_m,
    a.large_vessel_count,
    a.length_report_count,

    a.vw_avg_width_m,
    a.max_width_m,
    a.wide_vessel_count,

    a.vw_avg_draft_m,
    a.max_draft_m,
    a.p95_draft_m,
    a.deep_draft_count,
    a.draft_report_count,

    -- ── Draft imputation ─────────────────────────────
    -- Best available imputed draft, priority:
    --   1. Per-vessel type-stratified OLS from aggregate_ais.py
    --   2. Cell-level OLS regression (draft ~ length, R²≈0.63)
    --   3. Raw reported draft (when length also NULL)
    -- Clamped to [0.5, 25] metres.
    coalesce(
        a.vw_avg_draft_imputed_m,
        a.vw_avg_draft_m,
        case when a.vw_avg_length_m is not null
             then greatest(0.5, least(25.0,
                  r.draft_intercept + r.draft_slope * a.vw_avg_length_m
             ))
        end
    ) as draft_imputed_m,
    a.vw_avg_draft_m is null as draft_was_imputed,

    -- ── Course diversity (circular statistics) ───────
    a.avg_circ_cog_stddev,
    a.cross_vessel_circ_cog_stddev,
    a.cog_vessel_count,

    -- ── Day / Night ──────────────────────────────────
    a.day_unique_vessels,
    a.night_unique_vessels,
    a.vw_day_avg_speed_knots,
    a.vw_night_avg_speed_knots,
    a.day_high_speed_vessel_count,
    a.night_high_speed_vessel_count,

    -- ── Vessel type mix (vessel-weighted) ────────────
    a.fishing_vessels,
    a.tug_vessels,
    a.passenger_vessels,
    a.cargo_vessels,
    a.tanker_vessels,
    a.pleasure_vessels,
    a.military_vessels,

    -- ── Navigational status ──────────────────────────
    a.restricted_vessel_count,

    -- ── Speed-lethality (per-vessel, Jensen-correct) ─────────
    -- Prefer vw_avg_lethality computed per-vessel in aggregate_ais.py;
    -- fall back to cell-average approximation if column is NULL
    -- (i.e. data predates the per-vessel computation).
    coalesce(
        a.vw_avg_lethality,
        1.0 / (1.0 + exp(-(
            {{ var('vt_lethality_beta0') }}
          + {{ var('vt_lethality_beta1') }}
          * coalesce(a.vw_avg_speed_knots, 0)
        )))
    ) as speed_lethality_index,

    -- ── Risk fractions (per-vessel from aggregate_ais.py) ────
    -- Fraction of vessels at lethal speeds (≥10 kn)
    coalesce(
        a.high_speed_fraction,
        a.high_speed_vessel_count::float / nullif(a.unique_vessels, 0)
    ) as high_speed_fraction,

    -- Fraction of vessels with deep draft (>8m, vertical strike zone)
    coalesce(
        a.draft_risk_fraction,
        a.deep_draft_count::float / nullif(a.unique_vessels, 0)
    ) as draft_risk_fraction

from {{ source('marine_risk', 'ais_h3_summary') }} a
cross join draft_regression r
