-- Intermediate model: vessel transit density (VTD) per hex cell per month
--
-- Rolls up the ais_vtd_strata joint strata
-- (h3_cell, month, vessel_type, size_class, speed_bin) to the
-- (h3_cell, month) grain and attaches the Garrison et al. (2025)
-- taxon-agnostic ("generic") speed-lethality probability.
--
-- ═══════════════════════════════════════════════════════════════
-- WHY VTD INSTEAD OF PING COUNTS
-- ═══════════════════════════════════════════════════════════════
-- The IWC strike-risk reporting standard (Leaper et al. 2026,
-- SC/70/HIM/13) defines exposure as vessel *transit density* —
-- track-km swept per unit area — not raw AIS ping counts. Ping
-- counts conflate broadcast rate (Class A ≫ Class B) and dwell
-- time with actual transit. aggregate_ais.py --vtd apportions each
-- great-circle segment's length across the H3 cells it crosses
-- (track-km is conserved per segment), giving an unbiased exposure
-- surface.
--
-- ═══════════════════════════════════════════════════════════════
-- GARRISON SPEED-LETHALITY (TOUCHPOINT A — JENSEN-CORRECT)
-- ═══════════════════════════════════════════════════════════════
-- P(lethal | speed) is non-linear in speed, so averaging speed and
-- then applying the logistic underestimates lethality (Jensen's
-- inequality). Because the strata are already binned by narrow
-- speed bins (le10 / 10_12 / 12_15 / gt15), we apply the Garrison
-- logistic *per stratum* on its track-km-weighted mean speed, then
-- track-km-weight the resulting probabilities up to the cell-month.
-- The within-bin speed spread is small, so the residual Jensen bias
-- is negligible.
--
-- Coefficients are the REAL Garrison et al. (2025) Table 3 values
-- (Front. Mar. Sci. 11:1467387, non-humpback "other" curve,
-- β₁=0.129/kn). The seed maps our length bins onto Garrison's only
-- material size edge (108 m): small/medium → Garrison Large,
-- large/vlarge → Garrison XL. The 'generic' (other) curve is used
-- here for traffic screening; the full whale_taxon × size_class grid
-- in the seed is reserved for the Phase 4 mortality module.
--
-- Grain: one row per (h3_cell, month).

{{ config(
    indexes=[
        {'columns': ['h3_cell']},
        {'columns': ['h3_cell', 'month']},
    ]
) }}

with strata as (

    select
        h3_cell,
        month,
        vessel_type,
        size_class,
        speed_bin,
        track_km,
        n_segments,
        mean_implied_speed_kn,
        mean_vessel_mass_t,
        cell_area_km2,
        vtd_km_per_km2
    from {{ source('marine_risk', 'ais_vtd_strata') }}

),

garrison_generic as (

    -- Taxon-agnostic touchpoint-A coefficients, one row per size class
    select
        size_class,
        beta0,
        beta1
    from {{ ref('garrison_lethality_coeffs') }}
    where whale_taxon = 'generic'

),

stratum_lethality as (

    -- Attach the Garrison generic logistic per stratum (per narrow
    -- speed bin → Jensen-correct).
    select
        s.*,
        {{ garrison_lethality('s.mean_implied_speed_kn', 'g.beta0', 'g.beta1') }}
            as p_leth_generic
    from strata s
    left join garrison_generic g
        on s.size_class = g.size_class

)

select
    h3_cell,
    month,

    -- Exposure: total track-km and vessel transit density (km / km²)
    sum(track_km)                                       as total_track_km,
    sum(n_segments)                                     as n_segments,
    max(cell_area_km2)                                  as cell_area_km2,
    sum(vtd_km_per_km2)                                 as vtd_km_per_km2,

    -- Garrison generic lethality, track-km-weighted across strata
    sum(track_km * p_leth_generic)
        / nullif(sum(track_km), 0)                      as garrison_leth_generic,

    -- Diagnostic: track-km-weighted vessel mass (tonnes)
    sum(track_km * mean_vessel_mass_t)
        / nullif(
            sum(case when mean_vessel_mass_t is not null then track_km end),
            0
        )                                               as mean_vessel_mass_t,

    -- Diagnostic: track-km-weighted implied speed (knots)
    sum(track_km * mean_implied_speed_kn)
        / nullif(sum(track_km), 0)                      as mean_implied_speed_kn

from stratum_lethality
group by h3_cell, month
